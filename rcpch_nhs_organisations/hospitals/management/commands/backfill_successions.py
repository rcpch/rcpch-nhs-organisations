# python imports
import datetime

# django
from django.core.management.base import BaseCommand, CommandError
from django.apps import apps
from django.db import transaction

# RCPCH
from rcpch_nhs_organisations.hospitals.general_functions.ods_update import (
    get_organisation,
    _extract_succession_info,
)
from rcpch_nhs_organisations.hospitals.general_functions.membership import (
    backfill_trust_attributes,
    backfill_organisation_attributes,
)
from rcpch_nhs_organisations.hospitals.models import (
    Trust,
    TrustSuccession,
    TrustVersion,
    Organisation,
    OrganisationSuccession,
    OrganisationVersion,
)

from .image import rcpch_ascii_art

W = "\033[0m"  # white (normal)
R = "\033[31m"  # red
G = "\033[32m"  # green
O = "\033[33m"  # orange
B = "\033[34m"  # blue
BOLD = "\033[1m"


# Maps entity type -> config. `backfill_helper` is the
# backfill_<entity>_attributes callable used to write the closure version row
# for the predecessor (see `handle`). `name_field` is the attribute on the
# entity that holds its name (used for the successor-side name-change prompt
# on Predecessor events).
ENTITY_CONFIG = {
    "trust": {
        "model": Trust,
        "succession_model": TrustSuccession,
        "version_model": TrustVersion,
        "version_parent_field": "trust",
        "ods_code_field": "ods_code",
        "parent_fk_field": "predecessor",
        "backfill_helper": backfill_trust_attributes,
        "name_field": "name",
    },
    "organisation": {
        "model": Organisation,
        "succession_model": OrganisationSuccession,
        "version_model": OrganisationVersion,
        "version_parent_field": "organisation",
        "ods_code_field": "ods_code",
        "parent_fk_field": "predecessor",
        "backfill_helper": backfill_organisation_attributes,
        "name_field": "name",
    }
}


def _successor_legal_start(ord_record):
    """Return the successor entity's own Legal.Start date from its ODS record.

    This is the date the successor entity itself was established. Comparing
    it to a succession event's legal date distinguishes a true merger (new
    entity created on the merger date; Legal.Start == event date) from an
    acquisition (existing entity absorbed another; Legal.Start < event date).

    Returns a datetime.date, or None if the record has no Legal date.
    """
    for d in ord_record.get("Date", []):
        if d.get("Type") == "Legal":
            start = d.get("Start")
            if start:
                return datetime.date.fromisoformat(start)
    return None


def _detect_succession_type(successor_legal_start, ev_date):
    """Classify a succession event as 'merger' or 'acquisition'.

    - successor_legal_start == ev_date  -> 'merger' (new entity created fresh)
    - successor_legal_start < ev_date   -> 'acquisition' (existing entity absorbed another)
    - successor_legal_start is None       -> 'merger' (fallback; ODS missing the date)
    - successor_legal_start > ev_date     -> 'merger' (data anomaly; logged by caller)

    'split' and 'closure' are not auto-detected by this command: 'closure' is
    set by the deactivate_* helpers, and 'split' has no real-world cases yet.
    """
    if successor_legal_start is None:
        return "merger"
    if successor_legal_start == ev_date:
        return "merger"
    if successor_legal_start < ev_date:
        return "acquisition"
    # successor_legal_start > ev_date — data anomaly
    return "merger"


def _pre_merger_name(version_model, parent_field, successor, ev_date):
    """Look up the successor's pre-merger name from its version history.

    Returns the `name` of the version row whose valid_to == ev_date (the row
    that was closed by the merger), or None if no such row exists. This lets
    the command pre-populate the name prompt with a value the operator has
    already entered via the admin, rather than asking them to re-enter it.
    """
    row = version_model.objects.filter(
        **{parent_field: successor, "valid_to": ev_date}
    ).first()
    if row is None:
        return None
    return getattr(row, "name", None)


class Command(BaseCommand):
    help = (
        "Backfill succession rows (mergers, acquisitions, splits, closures) "
        "from the ODS Succs block for every entity in the database. The ODS "
        "/organisations/{ods_code} endpoint returns the complete Succs block "
        "regardless of when the succession happened, so this recovers the "
        "full historical merger chain — not just the last 185 days. "
        "See documentation/docs/developer/backfill.md."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--entity",
            type=str,
            required=True,
            choices=list(ENTITY_CONFIG.keys()),
            help="Entity type to backfill: trust or organisation. (PDUs are "
            "not in ODS, so they are not supported by this command.)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Report missing succession rows without creating them.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Maximum number of entities to process (for testing).",
        )

    def handle(self, *args, **options):
        entity_type = options["entity"]
        dry_run = options["dry_run"]
        limit = options["limit"]

        config = ENTITY_CONFIG[entity_type]
        model = config["model"]
        succession_model = config["succession_model"]
        version_model = config["version_model"]
        version_parent_field = config["version_parent_field"]
        ods_code_field = config["ods_code_field"]
        backfill_helper = config["backfill_helper"]
        name_field = config["name_field"]

        qs = model.objects.all()
        if limit:
            qs = qs[:limit]

        total = qs.count()
        self.stdout.write(
            B + f"Backfilling successions for {total} {entity_type}(s)..." + W
        )

        found_count = 0
        created_count = 0
        skipped_count = 0
        # Pass 2 counters
        establishment_count = 0
        name_backfill_count = 0
        name_unchanged_count = 0
        bridge_count = 0

        # ------------------------------------------------------------------
        # Pass 1: create missing succession rows and close predecessors.
        #
        # We collect the events that were actually applied so Pass 2 can
        # backfill the successor's name/establishment row for them. Collecting
        # them here (rather than backfilling inline) decouples the backfill
        # from iteration order: a predecessor iterated before its successor
        # would otherwise create the succession row and leave nothing for the
        # successor's iteration to do, so the name backfill would never run.
        # ------------------------------------------------------------------
        applied_events = []  # list of (successor, ev_date, ev_type, ord_record)

        for entity in qs:
            ods_code = getattr(entity, ods_code_field)
            # Fetch the full ODS record. The /organisations/{ods_code} endpoint
            # returns the complete Succs block regardless of when the succession
            # happened — this is not subject to the 185-day /sync limit.
            try:
                ord_record = get_organisation(
                    f"https://directory.spineservices.nhs.uk/ORD/2-0-0/organisations/{ods_code}"
                )
            except Exception as e:
                self.stdout.write(
                    O + f"  {ods_code}: could not fetch ODS record ({e})" + W
                )
                continue

            succession_events = _extract_succession_info(ord_record)
            if not succession_events:
                continue

            for ev in succession_events:
                target_ods_code = ev["target_ods_code"]
                ev_type = ev["type"]
                ev_date = ev["date"]

                # Look up the target entity in our database.
                target = model.objects.filter(
                    **{ods_code_field: target_ods_code}
                ).first()
                if target is None:
                    self.stdout.write(
                        O + f"  {ods_code}: {ev_type} → {target_ods_code} "
                        f"({ev_date}) — target not in database, skipping" + W
                    )
                    skipped_count += 1
                    continue

                # Check if a succession row already exists.
                # For "Successor" (this entity was absorbed into the target),
                # the row is predecessor=this entity, successor=target.
                # For "Predecessor" (this entity absorbed the target), the row
                # is predecessor=target, successor=this entity.
                if ev_type == "Successor":
                    predecessor, successor = entity, target
                else:  # Predecessor
                    predecessor, successor = target, entity

                existing = succession_model.objects.filter(
                    predecessor=predecessor,
                    successor=successor,
                    succession_date=ev_date,
                ).exists()

                # Detect the succession type by comparing the successor's own
                # Legal.Start (when it was established) to the event date. If
                # they are equal, the successor is a brand-new entity created
                # by the merger (a true merger); if the successor pre-exists
                # the event, it absorbed the target (an acquisition). ODS does
                # not surface this distinction directly.
                #
                # For a Successor event, `entity` is the predecessor being
                # closed, so its own ODS record (ord_record) is irrelevant
                # here — we need the successor's establishment date, which we
                # don't have without an extra fetch. We only need the type on
                # the Predecessor branch (where `entity` is the successor and
                # ord_record is its record), so we compute it there.
                if ev_type == "Predecessor":
                    successor_legal_start = _successor_legal_start(ord_record)
                    suggested_type = _detect_succession_type(
                        successor_legal_start, ev_date
                    )
                    # Collect a backfill candidate for Pass 2 for EVERY
                    # Predecessor event, even if the succession row already
                    # exists. If the predecessor was iterated first, its
                    # Successor event created the row; when we reach the
                    # successor's Predecessor event, `existing` is True and we
                    # continue past the create block — but we still need Pass 2
                    # to backfill the establishment/name row. Collecting here
                    # (before the `existing` check) ensures the backfill runs
                    # regardless of iteration order.
                    applied_events.append(
                        (successor, ev_date, suggested_type, ord_record, predecessor)
                    )
                    if (
                        successor_legal_start is not None
                        and successor_legal_start > ev_date
                    ):
                        self.stdout.write(
                            O + f"  Warning: {successor}'s Legal.Start "
                            f"({successor_legal_start}) is after the event "
                            f"date ({ev_date}) — data anomaly. Defaulting "
                            f"to 'merger'; please review via the admin." + W
                        )
                else:
                    # Successor event: we don't have the successor's ODS record
                    # to hand (it's `target`, not `entity`). Fall back to
                    # 'merger' as a placeholder; the operator can correct via
                    # the admin. (The type only matters for the name/establishment
                    # backfill in Pass 2, which runs on Predecessor events.)
                    suggested_type = "merger"
                    successor_legal_start = None

                if existing:
                    continue  # already recorded

                found_count += 1

                self.stdout.write("")
                self.stdout.write(
                    B + f"  {ods_code} ({entity})" + W
                )
                self.stdout.write(
                    f"  {ev_type} → {target_ods_code} ({target})"
                )
                self.stdout.write(f"  Legal date: {ev_date}")
                self.stdout.write(
                    f"  Suggested succession_type: {suggested_type}"
                )
                # The predecessor ceased to exist on ev_date in every ODS
                # succession type (merger / acquisition / split / closure), so
                # confirming this row also closes the predecessor: a closure
                # version row is written (active=False from ev_date) and the
                # entity row's `active` flag is flipped. This is the same write
                # the backfill-merger admin wizard performs.
                predecessor_already_closed = not getattr(predecessor, "active", True)
                if predecessor_already_closed:
                    self.stdout.write(
                        f"  Predecessor {predecessor} is already inactive — "
                        "only the succession row will be created."
                    )
                else:
                    self.stdout.write(
                        O + f"  This will also close {predecessor} "
                        f"(set active=False from {ev_date})." + W
                    )

                # For a "Predecessor" event (this entity absorbed the target),
                # this entity is the continuing successor. Pass 2 handles the
                # name/establishment backfill — for a true merger (new entity)
                # it writes an establishment row; for an acquisition it prompts
                # for the pre-merger name (pre-populated from the version table
                # if the operator has already entered it via the admin).
                if ev_type == "Predecessor":
                    if suggested_type == "merger" and (
                        successor_legal_start is not None
                        and successor_legal_start == ev_date
                    ):
                        self.stdout.write(
                            f"  {successor} is a new entity created by this "
                            f"merger (Legal.Start == {ev_date}). No name "
                            "prompt; an establishment row will be backfilled."
                        )
                    else:
                        self.stdout.write(
                            O + f"  {successor} may have had a different name "
                            f"before {ev_date}. Pass 2 will prompt for the "
                            "pre-merger name (pre-populated from the version "
                            "table if known); leave blank to skip." + W
                        )

                if dry_run:
                    self.stdout.write(
                        O + "  [dry-run] would create succession row" + W
                    )
                    if not predecessor_already_closed:
                        self.stdout.write(
                            O + f"  [dry-run] would close {predecessor} "
                            f"(active=False from {ev_date})." + W
                        )
                    if ev_type == "Predecessor":
                        self.stdout.write(
                            O + f"  [dry-run] Pass 2 would backfill "
                            f"{successor}'s establishment/name row." + W
                        )
                    continue

                # Interactive prompt: yes / no / skip
                try:
                    answer = input(
                        f"  Create succession row {predecessor} → {successor} "
                        f"on {ev_date}"
                        + ("" if predecessor_already_closed else
                            f" and close {predecessor}")
                        + "? [y/n/s=skip] "
                    )
                except EOFError:
                    self.stdout.write(O + "  No input — skipping." + W)
                    skipped_count += 1
                    continue

                answer = answer.strip().lower()
                if answer != "y":
                    if answer == "n":
                        self.stdout.write(O + "  Not created." + W)
                    else:
                        self.stdout.write(O + "  Skipped." + W)
                    skipped_count += 1
                    continue

                with transaction.atomic():
                    succession_model.objects.create(
                        predecessor=predecessor,
                        successor=successor,
                        succession_date=ev_date,
                        succession_type=suggested_type,
                        notes=f"Backfilled from ODS Succs block ({ev_type}).",
                    )
                    if not predecessor_already_closed:
                        # Write the closure version row (active=False from
                        # ev_date forward) and flip the entity row. Uses
                        # the same backfill_<entity>_attributes helper as
                        # the admin wizard so the write path is identical.
                        backfill_helper(
                            predecessor,
                            valid_from=ev_date,
                            valid_to=None,
                            active=False,
                        )
                        predecessor.active = False
                        predecessor.save(update_fields=["active"])
                created_count += 1
                self.stdout.write(G + "  Created." + W)
                if not predecessor_already_closed:
                    self.stdout.write(
                        G + f"  Closed {predecessor} (active=False "
                        f"from {ev_date})." + W
                    )

                # Record the applied Predecessor event for Pass 2. We only
                # need Predecessor events (where `entity` is the successor);
                # Successor events close this entity and have no successor-side
                # backfill. We also re-fetch the successor's ODS record in Pass 2
                # only when needed, so we don't carry ord_record around for
                # events where it isn't the successor's record.
                # (The backfill candidate was already collected above, before
                # the `existing` check, so that iteration order doesn't affect
                # whether Pass 2 runs.)

        # ------------------------------------------------------------------
        # Pass 2: backfill the successor's establishment/name row for each
        # applied Predecessor event.
        #
        # For a true merger (new entity, Legal.Start == ev_date): write an
        # establishment row at Legal.Start with the successor's current name,
        # replacing the baseline-migration row that starts at the baseline date.
        # No prompt — a new entity never had a different name.
        #
        # For an acquisition (existing entity, Legal.Start < ev_date): prompt
        # for the pre-merger name, pre-populated from the version row whose
        # valid_to == ev_date (the row the merger closed) if the operator has
        # already entered it via the admin. If supplied, backfill a name-change
        # row covering [Legal.Start, ev_date).
        # ------------------------------------------------------------------
        if applied_events and not dry_run:
            self.stdout.write("")
            self.stdout.write(
                B + f"Pass 2: backfilling successor name/establishment for "
                f"{len(applied_events)} event(s)..." + W
            )

        # Group by (successor, ev_date): a successor can have multiple
        # Predecessor events at the same date (e.g. R0A absorbed RW3 + RM2
        # on 2017-10-01) and events at different dates (R0A later acquired RW6
        # on 2021-10-01). Each date is a distinct backfill:
        #   - If Legal.Start == ev_date, the group is a true merger (new entity
        #     created on that date) -> one establishment row, no prompt.
        #   - Otherwise the group is an acquisition -> one name prompt.
        # The ord_record is the successor's own ODS record (the same for every
        # event on that successor), so any one will do. We collect the
        # predecessors for each group so the prompt can signpost what was
        # acquired.
        groups = {}
        for successor, ev_date, suggested_type, ord_record, predecessor in applied_events:
            key = (successor.pk, ev_date)
            if key not in groups:
                groups[key] = {
                    "successor": successor,
                    "ev_date": ev_date,
                    "suggested_type": suggested_type,
                    "ord_record": ord_record,
                    "predecessors": [],
                }
            groups[key]["predecessors"].append(predecessor)

        for group in groups.values():
            successor = group["successor"]
            ev_date = group["ev_date"]
            suggested_type = group["suggested_type"]
            ord_record = group["ord_record"]
            predecessors = group["predecessors"]
            if dry_run:
                continue
            successor_legal_start = _successor_legal_start(ord_record)
            # Read the current name from the ODS record, not the entity row.
            # ODS overwrites the Name in place when a trust is renamed, so the
            # ODS record always has the post-merger name. The entity row may
            # be stale (if the cron sync hasn't run since the rename), which
            # would cause the prompt to show the pre-merger name as "current"
            # and the operator to enter the same name — producing a backwards
            # or zero-length interval. If the ODS record has no Name, fall
            # back to the entity row.
            ods_name = ord_record.get("Name") or ""
            entity_name = getattr(successor, name_field, "") or ""
            current_name = ods_name or entity_name
            if ods_name and ods_name != entity_name:
                self.stdout.write(
                    O + f"  Note: {successor}'s name in the database "
                    f"('{entity_name}') differs from ODS ('{ods_name}'). "
                    "Using the ODS name as the current name. Run `cron` to "
                    "sync the entity row." + W
                )
                # Update the entity row so the database is consistent with
                # the version rows we're about to write. Without this, the
                # entity row would still have the stale pre-merger name after
                # the backfill, and the bridging row (which uses current_name)
                # would match the ODS name but not the entity row.
                setattr(successor, name_field, ods_name)
                successor.save(update_fields=[name_field])

            is_true_merger = (
                successor_legal_start is not None
                and successor_legal_start == ev_date
            )

            if is_true_merger:
                # True merger: new entity created on ev_date. Backfill an
                # establishment row at Legal.Start with the current name,
                # replacing the baseline-migration row. _backfill_version_row
                # handles the baseline replacement (it deletes the baseline
                # row if its valid_from is later than the new row's).
                backfill_helper(
                    successor,
                    valid_from=successor_legal_start,
                    valid_to=None,
                    **{name_field: current_name},
                    active=True,
                )
                self.stdout.write(
                    G + f"  Backfilled establishment row for {successor} "
                    f"at {successor_legal_start} (name='{current_name}')." + W
                )
                establishment_count += 1
                continue

            # Acquisition: prompt for the pre-merger name, pre-populated from
            # the version table if available.
            pre_populated = _pre_merger_name(
                version_model, version_parent_field, successor, ev_date
            )
            # If the ODS record has no Legal.Start, fall back to the
            # valid_from of the pre-populated version row (if the operator
            # already entered it via the admin with the correct establishment
            # date). Without this, the name backfill is undateable and skipped.
            if successor_legal_start is None and pre_populated is not None:
                existing_row = version_model.objects.filter(
                    **{version_parent_field: successor, "valid_to": ev_date}
                ).first()
                if existing_row is not None:
                    successor_legal_start = existing_row.valid_from
            # Signpost what was acquired so the operator can decide whether
            # a rename happened. Multiple predecessors at the same date are
            # listed together.
            pred_summary = ", ".join(str(p) for p in predecessors)
            prompt_default = (
                f" [default: {pre_populated}]" if pre_populated else ""
            )
            try:
                old_name = input(
                    f"  On {ev_date}, {successor} acquired {pred_summary}. "
                    f"Enter the pre-merger name for {successor} if it was "
                    f"renamed in the process{prompt_default}.\n"
                    f"  Leave blank if the name was unchanged: "
                )
            except EOFError:
                self.stdout.write(
                    O + "  No input — skipping name backfill." + W
                )
                old_name = ""
            if pre_populated and not old_name.strip():
                # Operator accepted the default by pressing Enter.
                old_name = pre_populated
            else:
                old_name = old_name.strip()
            if not old_name or old_name == current_name:
                self.stdout.write(
                    O + f"  Name unchanged for {successor} — no backfill needed." + W
                )
                name_unchanged_count += 1
                continue

            if successor_legal_start is None:
                # ODS does not expose a Legal.Start for this successor, and
                # no pre-populated version row is available to infer it from.
                # The operator is the source of truth — prompt for the
                # establishment date (look it up in ODS Trac or another
                # source). This is the same pattern used for the pre-merger
                # name, which is also not recoverable from ODS.
                self.stdout.write(
                    O + f"  ODS has no Legal.Start for {successor}. "
                    "The establishment date is needed to date the "
                    "name-change row." + W
                )
                try:
                    date_str = input(
                        f"  Establishment date for {successor} "
                        "(YYYY-MM-DD, leave blank to skip): "
                    )
                except EOFError:
                    self.stdout.write(
                        O + "  No input — skipping name backfill." + W
                    )
                    continue
                date_str = date_str.strip()
                if not date_str:
                    self.stdout.write(
                        O + f"  Skipped name backfill for {successor}." + W
                    )
                    continue
                try:
                    successor_legal_start = datetime.date.fromisoformat(date_str)
                except ValueError:
                    self.stdout.write(
                        R + f"  Invalid date '{date_str}' — skipping." + W
                    )
                    continue

            backfill_helper(
                successor,
                valid_from=successor_legal_start,
                valid_to=ev_date,
                **{name_field: old_name},
                active=True,
            )
            self.stdout.write(
                G + f"  Backfilled {successor} name '{old_name}' "
                f"({successor_legal_start} → {ev_date})." + W
            )
            name_backfill_count += 1

            # Bridge the gap between the merger date and the baseline
            # migration date. The baseline migration created a current row
            # (valid_to=None) with valid_from=installation_date. If the
            # merger happened before the baseline date (which it always does
            # for backfilled events), there's a gap: [ev_date, baseline_date)
            # has no version row, so an as-of query for a date in that
            # interval would find no row and crash. Insert a bridging row
            # covering [ev_date, baseline_date) with the successor's current
            # name and active=True, so the timeline is continuous.
            baseline_row = version_model.objects.filter(
                **{version_parent_field: successor, "valid_to__isnull": True}
            ).order_by("-valid_from").first()
            if baseline_row is not None and baseline_row.valid_from > ev_date:
                backfill_helper(
                    successor,
                    valid_from=ev_date,
                    valid_to=baseline_row.valid_from,
                    **{name_field: current_name},
                    active=True,
                )
                self.stdout.write(
                    G + f"  Bridged gap for {successor} "
                    f"({ev_date} → {baseline_row.valid_from})." + W
                )
                bridge_count += 1

        self.stdout.write("")
        self.stdout.write(B + "Summary:" + W)
        self.stdout.write(f"  Found (missing): {found_count}")
        if not dry_run:
            self.stdout.write(G + f"  Created: {created_count}" + W)
            self.stdout.write(O + f"  Skipped/refused: {skipped_count}" + W)
            self.stdout.write(B + "  Pass 2:" + W)
            self.stdout.write(G + f"    Establishment rows: {establishment_count}" + W)
            self.stdout.write(G + f"    Name backfills: {name_backfill_count}" + W)
            self.stdout.write(G + f"    Bridging rows: {bridge_count}" + W)
            self.stdout.write(O + f"    Name unchanged / skipped: {name_unchanged_count}" + W)
        self.stdout.write("done.")
        rcpch_ascii_art()
