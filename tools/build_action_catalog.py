"""Rebuild data/action_access_levels.csv from AWS's Service Authorization Reference.

The access level of every action comes from AWS's Service Authorization Reference. We read
it from the copy packaged with policy_sentry (MIT licence), which is generated from that
reference, so no network access is needed:

    pip install policy_sentry && python tools/build_action_catalog.py

Only the services this blueprint models are kept.
"""

import csv
import json
from importlib.resources import files
from pathlib import Path

SERVICES = ["iam", "sts", "s3", "dynamodb", "rds", "secretsmanager", "kms"]
OUT = Path(__file__).resolve().parents[1] / "data" / "action_access_levels.csv"


def main() -> None:
    source = files("policy_sentry") / "shared" / "data" / "iam-definition.json"
    definition = json.loads(source.read_text())
    rows = []
    for service in SERVICES:
        for name, privilege in definition[service]["privileges"].items():
            rows.append((f"{service}:{name}", privilege["access_level"]))
    rows.sort()
    with OUT.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["action", "accessLevel"])
        writer.writerows(rows)
    print(f"wrote {len(rows)} actions to {OUT}")


if __name__ == "__main__":
    main()
