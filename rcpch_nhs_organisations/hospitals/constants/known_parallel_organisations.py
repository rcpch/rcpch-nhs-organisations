"""
Known parallel organisation codes — organisations that ODS closed and replaced
with a new code under a successor trust, but where the engine's
candidate-successor detection could not (or cannot yet) automatically surface
the replacement.

This list is the curated source of truth for these mappings, used by the
``reconcile_ods`` review workflow and the admin approve-and-apply path. Each
entry maps the closed (predecessor) ODS code to its active successor code, with
the parent-trust bridge and a free-text rationale.

This is analogous to ``known_acquisitions.py`` for trusts: it exists for the
cases ODS succession semantics cannot disambiguate automatically, so a human
has confirmed the mapping. As the engine's candidate-successor detection
improves, some of these may be removed (the engine would surface them
directly as ``parallel-code`` review items with the correct candidate).

Each entry:

- ``predecessor_ods_code``: the closed ODS code (flagged ``diverged_from_ods``
  on the ``Organisation`` row when the parallel-code change is applied).
- ``successor_ods_code``: the active ODS code for the same physical site
  under the successor trust (recorded as ``ods_replacement_code``).
- ``predecessor_trust``: the ODS code of the predecessor trust.
- ``successor_trust``: the ODS code of the successor trust.
- ``name``: the name of the organisation (for reference / logging).
- ``notes``: free-text rationale.

See ``documentation/docs/developer/merger-handling.md`` → "Parallel active
codes" for the workflow.
"""

KNOWN_PARALLEL_ORGANISATIONS = [
    {
        "predecessor_ods_code": "RYV02",
        "successor_ods_code": "RBN52",
        "predecessor_trust": "RYV",
        "successor_trust": "RBN",
        "name": "Ormskirk and District General Hospital",
        "notes": (
            "RYV02 was closed in ODS and succeeded by RBN52 under a "
            "successor trust. The engine's candidate-successor detection "
            "did not surface RBN52, so the mapping is curated here."
        ),
    },
    {
        "predecessor_ods_code": "RVJJ8",
        "successor_ods_code": "RA7C2",
        "predecessor_trust": "RVJ",
        "successor_trust": "RA7",
        "name": "Weston General Hospital",
        "notes": (
            "RVJJ8 was closed in ODS and succeeded by RA7C2 under a "
            "successor trust. The engine's candidate-successor detection "
            "surfaced several potential options, so the correct mapping is curated here."
        ),
    },
    {
        "predecessor_ods_code": "R1C03",
        "successor_ods_code": "RW155",
        "predecessor_trust": "R1C",
        "successor_trust": "RW1",
        "name": "Western Community Hospital",
        "notes": (
            "R1C03 was closed in ODS and succeeded by RW155 under a "
            "successor trust. The engine's candidate-successor detection "
            "surfaced several potential options, so the correct mapping is curated here."
        ),
    },

    {
        "predecessor_ods_code": "R1C55",
        "successor_ods_code": "H8P9C",
        "predecessor_trust": "R1C",
        "successor_trust": "RW1",
        "name": "Community Paediatrics - West",
        "notes": (
            "R1C55 was closed in ODS and succeeded by H8P9C under a "
            "successor trust. The engine's candidate-successor detection "
            "surfaced no potential options, so the correct mapping is curated here."
        ),
    },
    {
        "predecessor_ods_code": "R1CA6",
        "successor_ods_code": "RW1YH",
        "predecessor_trust": "R1C",
        "successor_trust": "RW1",
        "name": "Community Paediatrics - N.Forest",
        "notes": (
            "R1CA6 was closed in ODS and succeeded by RW1YH under a "
            "successor trust. The engine's candidate-successor detection "
            "surfaced multiple potential options, so the correct mapping is curated here."
        ),
    },
    {
        "predecessor_ods_code": "R1CD1",
        "successor_ods_code": "",
        "predecessor_trust": "R1C",
        "successor_trust": "RW1",
        "name": "Adelaide Health Centre",
        "notes": (
            "R1CD1 was closed in ODS and subsumed under its "
            "successor trust. There is no correct mapping"
        ),
    },
    {
        "predecessor_ods_code": "RY905",
        "successor_ods_code": "D1Y9J",
        "predecessor_trust": "RY9",
        "successor_trust": "DAX",
        "name": "Ham Clinic",
        "notes": (
            "RY905 was closed in ODS and never succeeded by its "
            "successor trust. The engine's candidate-successor detection "
            "surfaced one potential option which is set here."
        ),
    },
]


"""
Items where it is not clear who the successor is so will sit unreconciled until they can be
{
    "predecessor_ods_code": "RY918",
    "successor_ods_code": "",
    "predecessor_trust": "RY9",
    "successor_trust": "DAX",
    "name": "HEART OF HOUNSLOW CENTRE FOR HEALTH",
    "notes": (
        "RY918 was closed in ODS and never succeeded by its "
        "successor trust. It provides children's services. The engine's candidate-successor detection "
        "surfaced no potential options, so the correct mapping is set here."
    ),
},
{
    "predecessor_ods_code": "RYV42",
    "successor_ods_code": "",
    "predecessor_trust": "RYV",
    "successor_trust": "RY3",
    "name": "Community Paediatrics",
    "notes": (
        "RYV42 was closed in ODS and never succeeded by its "
        "successor trust. It provides children's services. The engine's candidate-successor detection "
        "surfaced no potential options, so it remains unreconciled."
    ),
},
{
    "predecessor_ods_code": "RYVF7",
    "successor_ods_code": "",
    "predecessor_trust": "RYV",
    "successor_trust": "RY3",
    "name": "Community Paediatrics",
    "notes": (
        "RYVF7 was closed in ODS and never succeeded by its "
        "successor trust. It provides children's services. The engine's candidate-successor detection "
        "surfaced no potential options, so it remains unreconciled."
    ),
},
{
    "predecessor_ods_code": "R1C22",
    "successor_ods_code": "Y0Y5C",
    "predecessor_trust": "R1C",
    "successor_trust": "RW1",
    "name": "Battenburg Avenue Clinic",
    "notes": (
        "R1C22 was closed in ODS and succeeded by Y0Y5C under a "
        "successor trust. The engine's candidate-successor detection "
        "surfaced no potential options. There are two predecessor codes for the same clinic."
    )
},
{
    "predecessor_ods_code": "R1CE4",
    "successor_ods_code": "Y0Y5C",
    "predecessor_trust": "R1C",
    "successor_trust": "RW1",
    "name": "Battenburg Avenue Clinic",
    "notes": (
        "R1CE4 was closed in ODS and succeeded by R0Y5C under a "
        "successor trust. The engine's candidate-successor detection "
        "surfaced no potential options. There are two predecessor codes for the same clinic."
    )
},
{
    "predecessor_ods_code": "RVJ72",
    "successor_ods_code": "NLX",
    "predecessor_trust": "R1C",
    "successor_trust": "RA7",
    "name": "South Gloucestershire Health Community Health Services",
    "notes": (
        "RVJ72 was closed in ODS and succeeded by NLX under a "
        "successor trust. It is a run by Sirona Care & Health and delivers community adult and children's services. "
        "The engine's candidate-successor detection "
        "surfaced no potential options, so the correct mapping is curated here."
    )
},
{
    "predecessor_ods_code": "RVJT9",
    "successor_ods_code": "NLX",
    "predecessor_trust": "R1C",
    "successor_trust": "RA7",
    "name": "Eastgate House",
    "notes": (
        "RVJT9 was closed in ODS and never succeeded by its "
        "successor trust. It is a run by Sirona Care & Health and delivers community adult and children's services. "
        "The engine's candidate-successor detection "
        "surfaced no potential options, so the correct mapping is curated here."
    )
},
"""
