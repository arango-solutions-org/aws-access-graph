# Vendored AWS ontology

`aws.ttl` and `aws.shapes.ttl` are copied from
[arango-solutions-org/aws-ontology](https://github.com/arango-solutions-org/aws-ontology)
(MIT licence, see `LICENSE` in this folder). The namespace is
`https://w3id.org/arango-solutions/aws-ontology#`.

| | |
|---|---|
| Base | `main` at `b95a70a7ca70c8ef82bcd77f2e2b9ef849cc854d` (release 0.6.0) |
| Plus | `feat/security-aws-facts` at `382c8c406d155969e98ad1d116e1a880a142a33a` (execution role, instance profile, tags, access level, public exposure) |
| Plus | `feat/derived-effective-access` at `f54e471c1872c4566f1065ce6f2b0d65778e64b8` (hasEffectiveAccess, canRead, canWrite, canManagePermissions, isAdministrator) |
| `aws.ttl` sha256 | `9e253726d0604b950ea9f5066b060c326c5dd6cbc30f8954d8d123ef23529b12` |
| `aws.shapes.ttl` sha256 | `aa8519d77176326e491aacd350f00fb8534e7016dba2b4f99ec10946c27ddb6c` |

Both pull requests are open upstream. Once they are merged and released (expected 0.7.0),
replace these files with the release and update this table. `tests/test_ontology.py` checks
the checksums, so any change to these files is deliberate.

If the derived-access terms are not accepted upstream, move them into
`ontology/aws-security-ext.ttl` in this repo and load that alongside `aws.ttl`.
