"""
Known ICB acquisitions where an existing Integrated Care Board absorbs
territory from a dissolving ICB. ODS does not expose a ``Legal.Start`` for
existing ICBs that gain territory, so the ``backfill_successions`` command's
``Legal.Start == event date`` check cannot distinguish these from true
mergers. This list auto-classifies them as ``acquisition`` without
prompting.

This mirrors the ``KNOWN_ACQUISITIONS`` / ``KNOWN_ACQUISITIONS_NO_NAME_CHANGE``
pattern for trusts in ``known_acquisitions.py``.

Each entry maps a ``(successor_ods_code, succession_date)`` pair — the two
values the command already knows at Pass 2 time from the ODS ``Succs`` block
— to:

  - ``succession_type``: always ``acquisition`` for this table.
  - ``legal_start``: the successor's own establishment date (from the ODS
    ``Date`` block where available). Used to date the version row if needed.
  - ``notes``: free-text signposting what was acquired.

See `documentation/docs/developer/icb-history-planning.md` → "Known ICB
acquisitions" for the provenance of each row.
"""

import datetime

KNOWN_ICB_ACQUISITIONS = [
    {
        "successor_ods_code": "QRL",
        "successor_name": "NHS Hampshire and Isle of Wight Integrated Care Board",
        "legal_start": datetime.date(2017, 4, 1),
        "succession_date": datetime.date(2026, 4, 1),
        "notes": (
            "Existing ICB gains territory from Frimley (QNQ) in the 2026 "
            "ICB reorganisation. QNQ split 3-way: S0E4D (Thames Valley), "
            "S9B9J (Surrey and Sussex), QRL (Hampshire and Isle of Wight). "
            "Name unchanged."
        ),
    },
]


def lookup_known_icb_acquisition(successor_ods_code, succession_date):
    """Return the constants entry for a known ICB acquisition, or ``None``.

    Matches on ``(successor_ods_code, succession_date)`` — the two values
    the ``backfill_successions`` command already knows at Pass 2 time from
    the ODS ``Succs`` block.

    Falls back to matching on ``ods_code`` alone (for single-entry ICBs) so
    that date drift between ODS and the constants table does not cause a
    miss, mirroring ``lookup_known_acquisition`` for trusts.
    """
    # Exact match on (ods_code, succession_date)
    for entry in KNOWN_ICB_ACQUISITIONS:
        if (
            entry["successor_ods_code"] == successor_ods_code
            and entry["succession_date"] == succession_date
        ):
            return entry
    # Fallback: match on ods_code alone (single-entry ICBs)
    matches = [
        e
        for e in KNOWN_ICB_ACQUISITIONS
        if e["successor_ods_code"] == successor_ods_code
    ]
    if len(matches) == 1:
        return matches[0]
    return None
