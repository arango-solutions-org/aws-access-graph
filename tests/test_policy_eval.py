"""The derivation rules, checked on the reference scenarios (no database)."""


def edges(derived, who):
    return {(e, to) for (e, frm, to) in derived.edges if frm == who}


def test_administrators(derived):
    assert derived.admins == {"prod-admin-role", "platform-dev-admin", "platform-prod-admin"}


def test_direct_grants(derived):
    assert edges(derived, "web-role") == {("canRead", "static-assets")}
    assert edges(derived, "app-role") == {("canRead", "customer-data"), ("canWrite", "financial-exports"),
                                          ("canWrite", "app-data-key")}
    assert edges(derived, "webhook-role") == {("canWrite", "customer-data")}


def test_permission_rewrite(derived):
    assert ("canManagePermissions", "etl-pipeline-role") in edges(derived, "etl-service-user")


def test_boundary_caps_permissions(derived):
    # contractor-user's policy allows s3:* on *, but its boundary allows only reading static-assets
    assert edges(derived, "contractor-user") == {("canRead", "static-assets")}


def test_explicit_deny_wins(derived):
    auditor = edges(derived, "auditor-role")
    assert ("canRead", "customer-data") in auditor
    assert not any(to == "financial-exports" for _, to in auditor)


def test_same_account_only(derived):
    # dev identities never get grants on prod resources from identity policies
    assert edges(derived, "dev-deployer-role") == set()
    assert not any(frm.startswith("platform-dev-admin") and to == "customer-data" for (_, frm, to) in derived.edges)


def test_group_policies_reach_members(derived):
    prov = derived.edges[("canRead", "app-team-prod-user-1", "app-team-prod-logs")]
    assert prov["via"] == {"app-team-prod-developers"}
