"""The reference access patterns.

Each pattern has a case the queries should flag and a control they shouldn't. Every grant
is written as a real IAM policy (policy -> statement -> effect / action / resource); the
access edges the queries use are derived from these policies in the next step, never planted.

Flagged cases, by pattern:

* Indirect exposure: public-web-instance -> web-role -> app-role -> customer data.
  Control: private-app-instance reaches the same data but isn't public.
* Public workload running as admin: public-bastion-instance -> prod-admin-role.
* Public function writing sensitive data: public-webhook-function -> webhook-role.
* Environment bridge: dev-deployer-role (dev) -> prod-deployer-role -> prod-admin-role.
  Control: breakglass-user reaches prod-admin-role through an approved break-glass path.
* Permission-rewrite escalation: etl-service-user can manage etl-pipeline-role's permissions.
  Control: analyst-user only reads, through its own team's role.
* Ownership gaps: migration-scratch (no team) and archived-reports (team retired).
* Cross-team writes: etl-pipeline-role (data-team) writes financial-exports (owned by app-team).
  Control: app-role writes it too, but app-team owns it.

Controls for the derivation rules:

* Permission boundary: contractor-user has s3:* on *, capped by a boundary to static-assets.
* Explicit deny: auditor-role reads every bucket except financial-exports, which is denied.
"""

from __future__ import annotations

from .estate import Account, Estate, Statement

ACTIVE_TEAMS = ["app-team", "web-team", "platform-team", "security-team", "integration-team", "data-team"]


def objects(*buckets: str) -> list[str]:
    return [f"arn:aws:s3:::{b}/*" for b in buckets]


def plant(estate: Estate, dev: Account, prod: Account) -> None:
    e = estate

    # -- data stores -------------------------------------------------------------
    app_key = e.kms_key("app-data-key", prod, team="app-team")
    e.bucket("customer-data", prod, "confidential", team="app-team", key=app_key)
    e.bucket("financial-exports", prod, "restricted", team="app-team", key=app_key)
    e.bucket("deploy-artifacts", prod, "internal", team="platform-team")
    e.bucket("static-assets", prod, "public", team="web-team", public=True)
    e.bucket("analytics-events", prod, "confidential", team="data-team")
    e.bucket("migration-scratch", prod, "confidential")                       # no owning team
    e.bucket("archived-reports", prod, "confidential", team="retired-team")   # team no longer exists

    # -- roles and their permissions ---------------------------------------------
    web = e.role("web-role", prod, team="web-team", trusted_service="ec2.amazonaws.com")
    e.attach(web, e.managed_policy("web-static-read", [
        Statement(["s3:GetObject", "s3:ListBucket"], ["arn:aws:s3:::static-assets", *objects("static-assets")]),
    ], prod, team="web-team"))

    app = e.role("app-role", prod, team="app-team", trusted_service="ec2.amazonaws.com")
    e.attach(app, e.managed_policy("app-data-access", [
        Statement(["s3:GetObject"], objects("customer-data")),
        Statement(["s3:PutObject"], objects("financial-exports")),
        Statement(["kms:Decrypt", "kms:GenerateDataKey"], [e.arn("app-data-key")]),
    ], prod, team="app-team"))
    e.can_assume(web, app)                                     # web tier may call into the app tier

    webhook = e.role("webhook-role", prod, team="integration-team", trusted_service="lambda.amazonaws.com")
    e.attach(webhook, e.managed_policy("webhook-ingest", [
        Statement(["s3:PutObject"], objects("customer-data")),
    ], prod, team="integration-team"))

    admin_policy = e.aws_managed_policy("AdministratorAccess", [Statement(["*"], ["*"])])
    prod_admin = e.role("prod-admin-role", prod, team="platform-team")
    e.attach(prod_admin, admin_policy)

    prod_deployer = e.role("prod-deployer-role", prod, team="platform-team")
    e.attach(prod_deployer, e.managed_policy("prod-deploy", [
        Statement(["s3:PutObject", "s3:GetObject"], objects("deploy-artifacts")),
    ], prod, team="platform-team"))
    e.can_assume(prod_deployer, prod_admin)
    e.can_assume(prod_deployer, app)

    dev_deployer = e.role("dev-deployer-role", dev, team="platform-team")
    e.inline_policy(dev_deployer, "dev-deployer-inline", [
        Statement(["sts:AssumeRole"], [e.arn("prod-deployer-role")]),
    ])
    e.can_assume(dev_deployer, prod_deployer)                  # the environment bridge

    etl = e.role("etl-pipeline-role", prod, team="data-team")
    e.attach(etl, e.managed_policy("etl-pipeline", [
        Statement(["s3:GetObject"], objects("analytics-events")),
        Statement(["s3:PutObject"], objects("financial-exports", "migration-scratch")),
    ], prod, team="data-team"))

    reader = e.role("analytics-reader-role", prod, team="data-team")
    e.attach(reader, e.managed_policy("analytics-read", [
        Statement(["s3:GetObject", "s3:ListBucket"], ["arn:aws:s3:::analytics-events", *objects("analytics-events")]),
    ], prod, team="data-team"))

    auditor = e.role("auditor-role", prod, team="security-team")
    e.attach(auditor, e.aws_managed_policy("AmazonS3ReadOnlyAccess", [
        Statement(["s3:Get*", "s3:List*"], ["*"]),
    ]))
    e.inline_policy(auditor, "auditor-deny-restricted", [
        Statement(["s3:*"], ["arn:aws:s3:::financial-exports", *objects("financial-exports")], effect="Deny"),
    ])

    # -- users ---------------------------------------------------------------------
    dev_user = e.user("dev-user", dev, team="platform-team")
    ci_user = e.user("ci-service-user", dev, team="platform-team")
    e.can_assume(dev_user, dev_deployer)
    e.can_assume(ci_user, dev_deployer)

    breakglass = e.user("breakglass-user", prod, team="security-team", tags={"breakglass": "approved"})
    e.can_assume(breakglass, prod_admin)

    etl_user = e.user("etl-service-user", prod, team="data-team")
    e.can_assume(etl_user, etl)
    e.inline_policy(etl_user, "etl-service-user-inline", [
        Statement(["iam:AttachRolePolicy", "iam:PutRolePolicy"], [e.arn("etl-pipeline-role")]),
        Statement(["s3:PutObject"], objects("archived-reports")),
    ])

    analyst = e.user("analyst-user", prod, team="data-team")
    e.can_assume(analyst, reader)

    contractor = e.user("contractor-user", prod, team="app-team")
    e.attach(contractor, e.managed_policy("contractor-s3", [Statement(["s3:*"], ["*"])], prod, team="app-team"))
    e.set_boundary(contractor, e.boundary("contractor-boundary", prod, [
        Statement(["s3:GetObject", "s3:ListBucket"], ["arn:aws:s3:::static-assets", *objects("static-assets")]),
    ]))

    # -- workloads -------------------------------------------------------------------
    e.ec2_instance("public-web-instance", prod, e.instance_profile("web-instance-profile", prod, web, "web-team"),
                   public=True, team="web-team")
    e.ec2_instance("private-app-instance", prod, e.instance_profile("app-instance-profile", prod, app, "app-team"),
                   public=False, team="app-team")
    e.ec2_instance("public-bastion-instance", prod,
                   e.instance_profile("bastion-instance-profile", prod, prod_admin, "platform-team"),
                   public=True, team="platform-team", instance_type="t3.micro")
    e.lambda_function("public-webhook-function", prod, webhook, public=True, team="integration-team")
