"""
Shared serializer for the `*Succession` tables.

All four succession tables (`TrustSuccession`, `OrganisationSuccession`,
`IntegratedCareBoardSuccession`, `PaediatricDiabetesUnitSuccession`) have
the same shape: a `predecessor` FK, a `successor` FK (nullable for
closures), a `succession_date`, a `succession_type`, and `notes`. The
detail endpoints (`/trusts/{ods_code}/`, `/organisations/{ods_code}/`,
etc.) expose the chain as `predecessors` and `successors` arrays using
this serializer.

The identifier field name differs by entity type (`ods_code` for trusts,
organisations, ICBs; `pz_code` for PDUs), so the serializer is parameterised
by `code_field` and resolves the related entity's name at serialization
time.

See documentation/docs/developer/temporal-history.md § Succession walk
for the design.
"""
from rest_framework import serializers


class SuccessionLinkSerializer(serializers.Serializer):
    """
    Serialise one row of a `*Succession` table as seen from one side of the
    chain. Used by both the `predecessors` and `successors` arrays on the
    detail endpoints.

    `code_field` is the identifier field on the related entity — `ods_code`
    for trusts/organisations/ICBs, `pz_code` for PDUs. The related entity
    is the *other* side of the link: when serialising a predecessor link
    (rows where the resolved entity is the successor), the related entity
    is `predecessor`; when serialising a successor link (rows where the
    resolved entity is the predecessor), the related entity is `successor`.

    `related_attr` selects which side to read: `"predecessor"` or
    `"successor"`.
    """

    # The identifier of the related entity (predecessor or successor).
    # The key name is always `ods_code` in the JSON output for consistency
    # across entity types, even for PDUs (which use `pz_code` internally).
    ods_code = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    succession_date = serializers.DateField()
    succession_type = serializers.CharField()

    def __init__(self, *args, code_field="ods_code", related_attr="successor", **kwargs):
        # `code_field`: the model field on the related entity that holds its
        # identifier. `related_attr`: which FK on the succession row points
        # at the entity we want to serialise (`"predecessor"` or
        # `"successor"`).
        self.code_field = code_field
        self.related_attr = related_attr
        super().__init__(*args, **kwargs)

    def _related(self, obj):
        return getattr(obj, self.related_attr, None)

    def get_ods_code(self, obj):
        related = self._related(obj)
        if related is None:
            return None
        return getattr(related, self.code_field, None)

    def get_name(self, obj):
        related = self._related(obj)
        if related is None:
            return None
        return getattr(related, "name", None)
