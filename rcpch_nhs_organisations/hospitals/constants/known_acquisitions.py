"""
Known NHS trust acquisitions, split into two lists:

1. ``KNOWN_ACQUISITIONS`` — acquisitions where the acquiring (successor) trust
   was renamed and the pre-merger name is not recoverable from the ODS API.
   ODS overwrites the ``Name`` of an active renamed trust in place, so the old
   name is gone from the API by the time ``backfill_successions`` runs. This
   list is the authoritative source for those pre-merger names, confirmed
   against ODS Trac or another authoritative source. The command auto-backfills
   the name-change row without prompting.

2. ``KNOWN_ACQUISITIONS_NO_NAME_CHANGE`` — acquisitions where the successor
   was NOT renamed. The command's Pass 2 would otherwise prompt the operator
   for a pre-merger name; listing them here lets the command skip the prompt
   silently (counted as 'name unchanged'), falling back to the y/n/skip + date
   prompt only for acquisitions not in either list.

Both lists are consumed by the ``backfill_successions`` management command
(Pass 2).

Each entry maps a (successor_ods_code, succession_date) pair — the two values
the command already knows at Pass 2 time from the ODS `Succs` block — to:

  - ``pre_merger_name``: the name the successor traded under *before* the
    acquisition (i.e. the name that should appear on the version row covering
    ``[legal_start, rename_date)``).
  - ``legal_start``: the start of the name-change interval. This is the
    successor's own establishment date from the ODS ``Date`` block where ODS
    exposes one; otherwise it is the earliest date the pre-merger name is known
    to have been in use. It becomes the ``valid_from`` of the backfilled
    name-change row.
  - ``succession_date``: the acquisition's legal date from the ODS ``Succs``
    block. This is the second half of the lookup key. ODS sometimes reports a
    legal date that differs by a day or two from the operational rename date
    (e.g. RTG: legal 2018-06-30 vs operational 2018-07-01).
  - ``rename_date``: the date the successor adopted its post-merger name — i.e.
    the correct ``valid_to`` for the name-change row and ``valid_from`` for the
    bridging row. Defaults to ``succession_date`` when the two coincide (the
    common case); set explicitly when they differ. The lookup function falls
    back to matching on ``ods_code`` alone (for single-entry trusts) so that
    date drift between ODS and the doc table does not cause a miss.
  - ``successor_name``: the successor's current (post-merger) name, used for
    logging and for the bridging row.
  - ``notes``: free-text signposting what was acquired.

Trusts formed by a true merger (a new entity with a new ODS code) are NOT
listed here — a new entity never had a different name, so no name-change row is
needed and the command backfills an establishment row silently. A trust that
was *created* by a true merger and *later* acquired another trust appears here
for the later acquisition only; the merger itself is handled by the
establishment-row path.

See `documentation/docs/developer/backfill.md` → "Known acquisitions with a
pre-merger name change" for the provenance of each row.
"""

import datetime

KNOWN_ACQUISITIONS = [
    {
        "successor_ods_code": "RC9",
        "successor_name": "Bedfordshire Hospitals NHS Foundation Trust",
        "pre_merger_name": "Luton and Dunstable University Hospital",
        "legal_start": datetime.date(2020, 4, 1),
        "succession_date": datetime.date(2020, 4, 1),
        "notes": "acquired Bedford Hospital NHS Trust (RC1)",
    },
    {
        "successor_ods_code": "RQ3",
        "successor_name": "Birmingham Women's and Children's NHS Foundation Trust",
        "pre_merger_name": "Birmingham Children's Hospital NHS Foundation Trust",
        "legal_start": datetime.date(2017, 2, 1),
        "succession_date": datetime.date(2017, 2, 1),
        "notes": "acquired Birmingham Women's NHS Foundation Trust (RLU)",
    },
    {
        "successor_ods_code": "RDE",
        "successor_name": "East Suffolk and North Essex NHS Foundation Trust",
        "pre_merger_name": "Colchester Hospital University NHS Foundation Trust",
        "legal_start": datetime.date(2018, 7, 1),
        "succession_date": datetime.date(2018, 7, 1),
        "notes": "acquired The Ipswich Hospital NHS Trust (RGQ)",
    },
    {
        "successor_ods_code": "RTQ",
        "successor_name": "Gloucestershire Health and Care NHS Foundation Trust",
        "pre_merger_name": "2gether NHS Foundation Trust",
        "legal_start": datetime.date(2019, 10, 1),
        "succession_date": datetime.date(2019, 10, 1),
        "notes": "acquired Gloucestershire Care Services NHS Trust (R1J)",
    },
    {
        "successor_ods_code": "RAX",
        "successor_name": "Kingston Hospital NHS Foundation Trust",
        "pre_merger_name": "Kingston Hospital NHS Trust",
        "legal_start": datetime.date(2024, 11, 1),
        "succession_date": datetime.date(2024, 11, 1),
        "notes": "acquired Hounslow and Richmond Community Healthcare NHS Trust (RY9)",
    },
    {
        "successor_ods_code": "REM",
        "successor_name": "Liverpool University Hospitals NHS Foundation Trust",
        "pre_merger_name": "Aintree University Hospital NHS Foundation Trust",
        "legal_start": datetime.date(2019, 10, 1),
        "succession_date": datetime.date(2019, 10, 1),
        "notes": "acquired Royal Liverpool and Broadgreen University Hospitals NHS Trust (RQ6)",
    },
    {
        "successor_ods_code": "RW4",
        "successor_name": "Mersey Care NHS Foundation Trust",
        "pre_merger_name": "Mersey Care NHS Trust",
        "legal_start": datetime.date(2016, 7, 1),
        "succession_date": datetime.date(2016, 7, 1),
        "notes": "acquired Calderstones Partnership NHS Foundation Trust (RJX)",
    },
    {
        "successor_ods_code": "RRE",
        "successor_name": "MIDLANDS PARTNERSHIP NHS FOUNDATION TRUST",
        "pre_merger_name": "South Staffordshire and Shropshire Healthcare NHS Foundation Trust",
        "legal_start": datetime.date(2018, 6, 1),
        "succession_date": datetime.date(2018, 5, 31),
        "rename_date": datetime.date(2018, 6, 1),
        "notes": "acquired Staffordshire and Stoke-on-Trent Partnership NHS Trust (R1E). ODS reports the legal succession date as 2018-05-31; the operational rename happened on 2018-06-01, so rename_date differs from succession_date.",
    },
    {
        "successor_ods_code": "RY3",
        "successor_name": "East of England Community Health and Care NHS Trust",
        "pre_merger_name": "Norfolk Community Health and Care NHS Trust",
        "legal_start": datetime.date(2026, 4, 1),
        "succession_date": datetime.date(2026, 4, 1),
        "notes": "acquired Cambridgeshire Community Services NHS Trust (RYV)",
    },
    {
        "successor_ods_code": "RNN",
        "successor_name": "North Cumbria Integrated Care NHS Foundation Trust",
        "pre_merger_name": "North Cumbria University Hospitals NHS Trust",
        "legal_start": datetime.date(2019, 10, 1),
        "succession_date": datetime.date(2019, 10, 1),
        "notes": "acquired Cumbria Partnership NHS Foundation Trust",
    },
    {
        "successor_ods_code": "RM3",
        "successor_name": "Northern Care Alliance NHS Foundation Trust",
        "pre_merger_name": "Salford Royal NHS Foundation Trust",
        "legal_start": datetime.date(2001, 4, 1),
        "succession_date": datetime.date(2021, 10, 1),
        "notes": "acquired Pennine Acute Hospitals NHS Trust (RW6) on 2021-10-01; documented in Part 2.",
    },
    {
        "successor_ods_code": "RGN",
        "successor_name": "NORTH WEST ANGLIA NHS FOUNDATION TRUST",
        "pre_merger_name": "Peterborough and Stamford Hospitals NHS Foundation Trust",
        "legal_start": datetime.date(2017, 4, 1),
        "succession_date": datetime.date(2017, 4, 1),
        "notes": "acquired Hinchingbrooke Health Care NHS Trust (RQQ)",
    },
    {
        "successor_ods_code": "RH8",
        "successor_name": "ROYAL DEVON UNIVERSITY HEALTHCARE NHS FOUNDATION TRUST",
        "pre_merger_name": "Royal Devon and Exeter NHS Foundation Trust",
        "legal_start": datetime.date(2022, 4, 1),
        "succession_date": datetime.date(2022, 4, 1),
        "notes": "acquired Northern Devon Healthcare NHS Trust (RBZ)",
    },
    {
        "successor_ods_code": "RAL",
        "successor_name": "ROYAL FREE LONDON NHS FOUNDATION TRUST",
        "pre_merger_name": "Royal Free Hampstead NHS Trust",
        "legal_start": datetime.date(2014, 7, 1),
        "succession_date": datetime.date(2014, 7, 2),
        "rename_date": datetime.date(2014, 7, 1),
        "notes": "acquired Barnet and Chase Farm Hospitals NHS Trust (RVL). ODS reports the legal succession date as 2014-07-02; the operational rename happened on 2014-07-01, so rename_date differs from succession_date.",
    },
    {
        "successor_ods_code": "RH5",
        "successor_name": "Somerset NHS Foundation Trust",
        "pre_merger_name": "Somerset Partnership NHS Foundation Trust",
        "legal_start": datetime.date(2020, 4, 1),
        "succession_date": datetime.date(2020, 4, 1),
        "notes": "acquired Taunton and Somerset NHS Foundation Trust (RBA)",
    },
    {
        "successor_ods_code": "RH5",
        "successor_name": "Somerset NHS Foundation Trust",
        "pre_merger_name": "Somerset NHS Foundation Trust",
        "legal_start": datetime.date(2023, 4, 1),
        "succession_date": datetime.date(2023, 4, 1),
        "notes": "acquired Yeovil District Hospital NHS Foundation Trust (RA4); name unchanged.",
    },
    {
        "successor_ods_code": "RW1",
        "successor_name": "HAMPSHIRE AND ISLE OF WIGHT HEALTHCARE NHS FOUNDATION TRUST",
        "pre_merger_name": "Southern Health NHS Foundation Trust",
        "legal_start": datetime.date(2011, 4, 1),
        "succession_date": datetime.date(2024, 10, 1),
        "rename_date": datetime.date(2024, 10, 1),
        "notes": "acquired Solent NHS Trust (R1C) and others on 2024-10-01; renamed from Southern Health NHS FT to Hampshire and Isle of Wight Healthcare NHS FT. legal_start is 2011-04-01 (when the 'Southern Health' name was adopted after the earlier Hampshire Partnership + Hampshire Community Healthcare merger). NOTE: the 2011-04-01 rename (Hampshire Partnership → Southern Health) is NOT in ODS's Succs block for RW1, so this command cannot backfill it — it must be done manually via the admin or the backfill_trust_attributes helper.",
    },
    {
        "successor_ods_code": "RBN",
        "successor_name": "Mersey and West Lancashire Teaching Hospitals NHS Trust",
        "pre_merger_name": "ST HELENS AND KNOWSLEY TEACHING HOSPITALS NHS TRUST",
        "legal_start": datetime.date(2023, 7, 1),
        "succession_date": datetime.date(2023, 7, 1),
        "notes": "acquired Southport and Ormskirk Hospital NHS Trust (RVY)",
    },
    {
        "successor_ods_code": "RAJ",
        "successor_name": "MID AND SOUTH ESSEX NHS FOUNDATION TRUST",
        "pre_merger_name": "Southend University Hospital NHS Foundation Trust",
        "legal_start": datetime.date(2020, 4, 1),
        "succession_date": datetime.date(2020, 4, 1),
        "notes": "acquired Basildon and Thurrock University Hospitals NHS Foundation Trust and Mid Essex Hospital Services NHS Trust",
    },
    {
        "successor_ods_code": "RA9",
        "successor_name": "TORBAY AND SOUTH DEVON NHS FOUNDATION TRUST",
        "pre_merger_name": "South Devon Healthcare NHS Foundation Trust",
        "legal_start": datetime.date(2015, 10, 1),
        "succession_date": datetime.date(2015, 10, 1),
        "notes": "acquired Torbay and Southern Devon Health and Care NHS Trust (R1G)",
    },
    # RRK (University Hospitals Birmingham) acquiring RR1 (Heart of England) on
    # 2018-04-02 is listed in KNOWN_ACQUISITIONS_NO_NAME_CHANGE below — the
    # only "change" was casing (Title Case -> ALL CAPS), not a real rename.
    {
        "successor_ods_code": "RA7",
        "successor_name": "UNIVERSITY HOSPITALS BRISTOL AND WESTON NHS FOUNDATION TRUST",
        "pre_merger_name": "University Hospitals Bristol NHS Foundation Trust",
        "legal_start": datetime.date(2020, 4, 1),
        "succession_date": datetime.date(2020, 4, 1),
        "notes": "acquired Weston Area Health NHS Trust (RA3)",
    },
    {
        "successor_ods_code": "RA7",
        "successor_name": "Bristol NHS Foundation Trust",
        "pre_merger_name": "University Hospitals Bristol and Weston NHS Foundation Trust",
        "legal_start": datetime.date(2026, 7, 1),
        "succession_date": datetime.date(2026, 7, 1),
        "notes": "acquired North Bristol NHS Trust (RVJ)",
    },
    {
        "successor_ods_code": "RTG",
        "successor_name": "UNIVERSITY HOSPITALS OF DERBY AND BURTON NHS FOUNDATION TRUST",
        "pre_merger_name": "Derby Teaching Hospitals NHS Foundation Trust",
        "legal_start": datetime.date(2018, 7, 1),
        "succession_date": datetime.date(2018, 6, 30),
        "rename_date": datetime.date(2018, 7, 1),
        "notes": "acquired Burton Hospitals NHS Foundation Trust (RJF). ODS reports the legal succession date as 2018-06-30; the operational rename to UHDB happened on 2018-07-01, so rename_date differs from succession_date.",
    },
    {
        "successor_ods_code": "RYR",
        "successor_name": "UNIVERSITY HOSPITALS SUSSEX NHS FOUNDATION TRUST",
        "pre_merger_name": "Western Sussex Hospitals NHS Foundation Trust",
        "legal_start": datetime.date(2021, 4, 1),
        "succession_date": datetime.date(2021, 4, 1),
        "notes": "acquired Brighton and Sussex University Hospitals NHS Trust (RXH)",
    },
    {
        "successor_ods_code": "RWW",
        "successor_name": "North Cheshire and Mersey NHS Foundation Trust",
        "pre_merger_name": "WARRINGTON AND HALTON TEACHING HOSPITALS NHS FOUNDATION TRUST",
        "legal_start": datetime.date(2026, 4, 1),
        "succession_date": datetime.date(2026, 4, 1),
        "notes": "acquired Bridgewater Community Healthcare NHS Foundation Trust (RY2)",
    },
]


# ---------------------------------------------------------------------------
# Acquisitions where the successor trust was NOT renamed.
#
# These are acquisitions (an existing trust absorbed another) where the
# successor's name did not change. The `backfill_successions` command's Pass 2
# would otherwise prompt the operator for a pre-merger name for these; listing
# them here lets the command skip the prompt silently (counted as
# 'name unchanged'), falling back to the y/n/skip + date prompt only for
# acquisitions not in either list.
#
# Each entry maps a (successor_ods_code, succession_date) pair to a notes
# string. The succession_date is the ODS `Succs` legal date (verified against
# the ODS API). A trust with multiple no-name-change acquisitions (e.g. RW4
# Mersey Care) has multiple entries with different succession_date values.
#
# RRK (University Hospitals Birmingham) acquiring RR1 (Heart of England) on
# 2018-04-02 is listed here, not in KNOWN_ACQUISITIONS, because the only
# "change" was casing (Title Case -> ALL CAPS), not a real rename.
# ---------------------------------------------------------------------------

KNOWN_ACQUISITIONS_NO_NAME_CHANGE = [
    {
        "successor_ods_code": "RQM",
        "successor_name": "CHELSEA AND WESTMINSTER HOSPITAL NHS FOUNDATION TRUST",
        "succession_date": datetime.date(2015, 9, 1),
        "notes": "acquired West Middlesex University Hospital NHS Trust (RFW); name unchanged.",
    },
    {
        "successor_ods_code": "RJ1",
        "successor_name": "GUY'S AND ST THOMAS' NHS FOUNDATION TRUST",
        "succession_date": datetime.date(2021, 2, 1),
        "notes": "acquired Royal Brompton & Harefield NHS Foundation Trust (RT3); name unchanged.",
    },
    {
        "successor_ods_code": "R0A",
        "successor_name": "MANCHESTER UNIVERSITY NHS FOUNDATION TRUST",
        "succession_date": datetime.date(2021, 10, 1),
        "notes": "acquired Pennine Acute Hospitals NHS Trust (RW6); name unchanged. (R0A was created by a true merger of RM2+RW3 on 2017-10-01, which takes the establishment-row path; this is the later RW6 acquisition.)",
    },
    {
        "successor_ods_code": "RW4",
        "successor_name": "MERSEY CARE NHS FOUNDATION TRUST",
        "succession_date": datetime.date(2018, 3, 31),
        "notes": "acquired Liverpool Community Health NHS Trust (RY1); name unchanged.",
    },
    {
        "successor_ods_code": "RW4",
        "successor_name": "MERSEY CARE NHS FOUNDATION TRUST",
        "succession_date": datetime.date(2021, 6, 1),
        "notes": "acquired North West Boroughs Healthcare NHS Foundation Trust (RTV); name unchanged.",
    },
    {
        "successor_ods_code": "RAL",
        "successor_name": "ROYAL FREE LONDON NHS FOUNDATION TRUST",
        "succession_date": datetime.date(2025, 1, 1),
        "notes": "acquired North Middlesex University Hospital NHS Trust (RAP); name unchanged. (RAL's earlier 2014-07-02 acquisition of RVL is in KNOWN_ACQUISITIONS with a name change.)",
    },
    {
        "successor_ods_code": "RRK",
        "successor_name": "UNIVERSITY HOSPITALS BIRMINGHAM NHS FOUNDATION TRUST",
        "succession_date": datetime.date(2018, 4, 2),
        "notes": "acquired Heart of England NHS Foundation Trust (RR1); name unchanged (only casing changed: Title Case -> ALL CAPS).",
    },
]


def lookup_known_acquisition(successor_ods_code, succession_date):
    """Return the constants entry for a known acquisition WITH a name change, or ``None``.

    Matches on ``(successor_ods_code, succession_date)`` — the two values the
    ``backfill_successions`` command already knows at Pass 2 time from the ODS
    ``Succs`` block. A trust with multiple acquisitions (e.g. RH5 Somerset,
    RA7 Bristol) has multiple entries with different ``succession_date``
    values, so the match is unambiguous.

    ODS sometimes reports a legal succession date that differs by a day or two
    from the operational rename date recorded in the doc table (e.g. RTG:
    legal 2018-06-30 vs operational 2018-07-01; RRK: legal 2018-04-02 vs
    operational 2018-04-01). If the constants entry was authored against the
    operational date, the exact-date lookup will miss. To tolerate this, when
    the exact match fails we fall back to matching on ``successor_ods_code``
    alone — but only if there is exactly one entry for that trust, so the
    multi-acquisition trusts (RH5, RA7) remain unambiguous and are not
    matched by the fallback. The returned entry's ``rename_date`` (which may
    differ from ``succession_date``) is the authoritative ``valid_to`` for
    the name-change row.
    """
    # Exact match first.
    for entry in KNOWN_ACQUISITIONS:
        if (
            entry["successor_ods_code"] == successor_ods_code
            and entry["succession_date"] == succession_date
        ):
            return entry
    # Fallback: match on ods_code alone, but only if there is exactly one
    # entry for that trust (so multi-acquisition trusts are not matched
    # ambiguously). This handles the legal-vs-operational date drift.
    matches = [
        e for e in KNOWN_ACQUISITIONS
        if e["successor_ods_code"] == successor_ods_code
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def lookup_known_acquisition_no_name_change(successor_ods_code, succession_date):
    """Return the constants entry for a known acquisition with NO name change, or ``None``.

    Matches on ``(successor_ods_code, succession_date)`` — the ODS ``Succs``
    legal date. Used by ``backfill_successions`` Pass 2 to skip the name prompt
    silently for acquisitions where the successor was not renamed, falling back
    to the y/n/skip + date prompt only for acquisitions not in either list.

    A trust with multiple no-name-change acquisitions (e.g. RW4 Mersey Care:
    RY1 on 2018-03-31 and RTV on 2021-06-01) has multiple entries with
    different ``succession_date`` values, so the match is unambiguous. No
    ods_code-only fallback is applied here, since the no-name-change entries
    are verified against ODS and the dates match exactly.
    """
    for entry in KNOWN_ACQUISITIONS_NO_NAME_CHANGE:
        if (
            entry["successor_ods_code"] == successor_ods_code
            and entry["succession_date"] == succession_date
        ):
            return entry
    return None
