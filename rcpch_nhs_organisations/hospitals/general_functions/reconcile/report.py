"""
Categorised markdown report for the reconciliation engine.

Actionable items first, grouped by level and change class. Legacy "predecessor
not in DB" entries are collapsed into a single count, not 350 lines (the issue
#172 noise). An empty actionable report renders as an empty string so the ODS
change-detection blob → GitHub-issue path treats it as "no changes".
"""

# Human-readable ordering for the report.
LEVEL_ORDER = ["organisation", "trust", "lhb", "icb"]
LEVEL_TITLES = {
    "organisation": "Organisations",
    "trust": "Trusts",
    "lhb": "Local Health Boards",
    "icb": "Integrated Care Boards",
}
CLASS_ORDER = [
    "succession",
    "superseded-code",
    "relationship",
    "roster-add",
    "retire",
    "parallel-code",
    "attribute",
]
CLASS_TITLES = {
    "attribute": "Attribute changes",
    "relationship": "Relationship (re-parenting) changes",
    "succession": "Successions (merger / acquisition / split / closure)",
    "superseded-code": "Superseded organisation codes",
    "roster-add": "New entities in ODS (roster add)",
    "retire": "Retirements / status mismatches",
    "parallel-code": "Parallel active codes",
}


def build_report(result):
    """Render a DetectionResult as categorised markdown. Returns "" if nothing
    actionable was found (fetch errors and the legacy-skip count alone do not
    make a report non-empty)."""
    lines = []
    changes = result.changes

    for level in LEVEL_ORDER:
        level_changes = [c for c in changes if c.level == level]
        if not level_changes:
            continue
        lines.append(f"## {LEVEL_TITLES[level]}")
        lines.append("")
        for change_class in CLASS_ORDER:
            class_changes = [c for c in level_changes if c.change_class == change_class]
            if not class_changes:
                continue
            lines.append(f"### {CLASS_TITLES[change_class]}")
            lines.append("")
            for c in sorted(class_changes, key=lambda c: c.ods_code):
                suffix = " _(auto-applied)_" if c.auto_safe else ""
                date = f" [{c.effective_date.isoformat()}]" if c.effective_date else ""
                lines.append(f"- **{c.ods_code}**{date}: {c.summary}{suffix}")
            lines.append("")

    report = "\n".join(lines).strip()

    # Footer: collapsed legacy-skip count and fetch errors, only appended when
    # there is already actionable content (so an otherwise-empty report stays
    # empty for the "no changes" signal).
    footer = []
    if result.legacy_skips:
        footer.append(
            f"_Collapsed {result.legacy_skips} legacy pre-floor succession "
            "reference(s) (predecessor/target not in database before the "
            "2020-12-01 temporal floor)._"
        )
    if result.fetch_errors:
        codes = ", ".join(f"{lvl}:{code}" for lvl, code in result.fetch_errors)
        footer.append(f"_Could not deep-fetch {len(result.fetch_errors)} entity(ies): {codes}._")

    if report and footer:
        report = report + "\n\n" + "\n\n".join(footer)
    return report + "\n" if report else ""
