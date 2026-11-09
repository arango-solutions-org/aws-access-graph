# Vendored AWS ontology

`aws.ttl` and `aws.shapes.ttl` are copied from
[arango-solutions-org/aws-ontology](https://github.com/arango-solutions-org/aws-ontology)
(MIT licence, see `LICENSE` in this folder). The namespace is
`https://w3id.org/arango-solutions/aws-ontology#`.

| | |
|---|---|
| Source | `main` at `9ea0fb7897811e9ae2c1fb84ba751dea5669916f` (after release 0.6.0) |
| Includes | #5 execution role, instance profile, tags, access level, public exposure |
| Includes | #6 derived effective access: `hasEffectiveAccess`, one sub-property per access level, `isAdministrator` |
| Includes | #17 a domain and range on every property (REQ-016) |
| `aws.ttl` sha256 | `9a9bda99f43494e37353f5b25941a2ae9c9ade2c84ecfc29b32dfffc5ab61cc7` |
| `aws.shapes.ttl` sha256 | `7611598f04f75fd9c465e5da91d58a5de9e0da0e754831e1fa90353e04473e1a` |

Once these changes are released (expected 0.7.0), replace these files with the release and
update this table. `tests/test_ontology.py` checks the checksums, so any change to these files
is deliberate.
