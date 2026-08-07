"""
Seeded ODS organisation codes that ODS considers Inactive but that the
RCPCH audit system still uses, because the physical site is still open and
still under the same parent trust. ODS retired the code for administrative
reasons (re-coding, issuing a parallel record, folding into a parent site),
not because the site closed.

These codes are flagged on the `Organisation` model via `diverged_from_ods`
(with the active replacement code in `ods_replacement_code` where one
exists) so that:

- the backfill does not treat the ODS closure date as the membership end
  date for these sites (the membership is extended to "now");
- the consuming software can identify divergent codes and, when ready,
  flip its references from `ods_code` to `ods_replacement_code`;
- future maintainers can find the curated rationale for each divergence
  in one place.

`ods_replacement_code` is the active ODS code for the same site, where one
exists. When the consuming software is ready to switch, the fix is to
update its references from `ods_code` to `ods_replacement_code`. A null
`ods_replacement_code` means ODS folded the site into a parent site record
rather than issuing a twin — the fix requires a decision, not a simple
remap.

See `documentation/docs/developer/backfill.md` "ODS-divergent organisation
codes" for the full rationale and the table of known cases.
"""

ODS_DIVERGENT_ORGANISATIONS = [
    {
        "ods_code": "R1APF",
        "name": "COVERCROFT",
        "parent_trust": "R1A",
        "ods_status": "Inactive",
        "ods_closure_date": "2023-05-31",
        "ods_replacement_code": "R1A1R",
        "ods_replacement_name": "COVER CROFT CENTRE",
        "notes": (
            "Same address (Colman Road, Droitwich, WR9 8QU), same parent "
            "trust (Herefordshire & Worcestershire Health and Care NHS "
            "Trust). ODS ran two codes in parallel from 2011-06-22 until "
            "R1APF was closed on 2023-05-31; R1A1R remains active. The "
            "consuming software references R1APF, so the code is retained "
            "and the membership is extended to now. When the consuming "
            "software is ready to switch, flip references from R1APF to "
            "R1A1R."
        ),
    },
]
