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
        "predecessor_trust": "RYV",  # TODO: confirm predecessor trust
        "successor_trust": "RBN",  # TODO: confirm successor trust
        "name": "",  # TODO: confirm organisation name
        "notes": (
            "RYV02 was closed in ODS and succeeded by RBN52 under a "
            "successor trust. The engine's candidate-successor detection "
            "did not surface RBN52, so the mapping is curated here."
        ),
    },
]
