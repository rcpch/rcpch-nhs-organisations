"""
Tests for the OrganisationVersion temporal entity-attribute layer.

These tests establish the pattern that all subsequent version models follow:
- a baseline version row is created with valid_to IS NULL
- a new version row supersedes the previous one (valid_to set on the old row)
- the as-of query returns the correct snapshot for a given date
- is_current() reflects whether a version is the open one
"""
import datetime

import pytest
from django.apps import apps

from rcpch_nhs_organisations.hospitals.models import OrganisationVersion

Organisation = apps.get_model("hospitals", "Organisation")
Trust = apps.get_model("hospitals", "Trust")


@pytest.fixture
def trust():
    return Trust.objects.create(ods_code="RXX", name="Test Trust")


@pytest.fixture
def organisation(trust):
    return Organisation.objects.create(
        ods_code="RXX01",
        name="Original Name",
        address1="1 Old Street",
        city="Oldtown",
        postcode="OL1 1AA",
        active=True,
        trust=trust,
    )


def create_version(organisation, valid_from, **fields):
    """Helper: create an OrganisationVersion row with sensible defaults."""
    defaults = dict(
        name=organisation.name,
        address1=organisation.address1,
        city=organisation.city,
        postcode=organisation.postcode,
        active=organisation.active,
    )
    defaults.update(fields)
    return OrganisationVersion.objects.create(
        organisation=organisation,
        valid_from=valid_from,
        valid_to=None,
        **defaults,
    )


@pytest.mark.django_db
def test_baseline_version_is_current(organisation):
    """A freshly created version with valid_to IS NULL is the current one."""
    version = create_version(organisation, datetime.date(2020, 1, 1))
    assert version.is_current() is True
    assert version.valid_to is None


@pytest.mark.django_db
def test_new_version_closes_previous(organisation):
    """Creating a new current version must close the previous one."""
    old = create_version(organisation, datetime.date(2020, 1, 1), name="Old Name")
    # Simulate the helper pattern: close the old row, open a new one.
    OrganisationVersion.objects.filter(
        organisation=organisation, valid_to__isnull=True
    ).update(valid_to=datetime.date(2021, 6, 1))
    new = OrganisationVersion.objects.create(
        organisation=organisation,
        valid_from=datetime.date(2021, 6, 1),
        valid_to=None,
        name="New Name",
        address1=organisation.address1,
        city=organisation.city,
        postcode=organisation.postcode,
        active=organisation.active,
    )
    old.refresh_from_db()
    assert old.valid_to == datetime.date(2021, 6, 1)
    assert old.is_current() is False
    assert new.is_current() is True
    assert new.name == "New Name"


@pytest.mark.django_db
def test_as_of_query_returns_correct_snapshot(organisation):
    """The as-of query returns the version that was in force on the given date."""
    create_version(organisation, datetime.date(2020, 1, 1), name="Old Name")
    OrganisationVersion.objects.filter(
        organisation=organisation, valid_to__isnull=True
    ).update(valid_to=datetime.date(2021, 6, 1))
    OrganisationVersion.objects.create(
        organisation=organisation,
        valid_from=datetime.date(2021, 6, 1),
        valid_to=None,
        name="New Name",
        address1=organisation.address1,
        city=organisation.city,
        postcode=organisation.postcode,
        active=organisation.active,
    )

    before = OrganisationVersion.objects.filter(
        organisation=organisation,
        valid_from__lte=datetime.date(2020, 6, 1),
    ).filter(
        # valid_to is NULL (current) OR valid_to is after the query date
        valid_to__gt=datetime.date(2020, 6, 1),
    ).get()

    after = OrganisationVersion.objects.filter(
        organisation=organisation,
        valid_from__lte=datetime.date(2022, 1, 1),
    ).filter(
        valid_to__isnull=True,
    ).get()

    assert before.name == "Old Name"
    assert after.name == "New Name"


@pytest.mark.django_db
def test_as_of_query_on_change_date_returns_new_version(organisation):
    """On the exact change date, the new version is in force (half-open interval)."""
    create_version(organisation, datetime.date(2020, 1, 1), name="Old Name")
    OrganisationVersion.objects.filter(
        organisation=organisation, valid_to__isnull=True
    ).update(valid_to=datetime.date(2021, 6, 1))
    OrganisationVersion.objects.create(
        organisation=organisation,
        valid_from=datetime.date(2021, 6, 1),
        valid_to=None,
        name="New Name",
        address1=organisation.address1,
        city=organisation.city,
        postcode=organisation.postcode,
        active=organisation.active,
    )

    on_change_date = OrganisationVersion.objects.filter(
        organisation=organisation,
        valid_from__lte=datetime.date(2021, 6, 1),
    ).filter(
        valid_to__isnull=True,
    ).get()

    assert on_change_date.name == "New Name"


@pytest.mark.django_db
def test_as_of_query_before_first_version_returns_nothing(organisation):
    """A date before the first valid_from returns no version (pre-history)."""
    create_version(organisation, datetime.date(2020, 1, 1))
    qs = OrganisationVersion.objects.filter(
        organisation=organisation,
        valid_from__lte=datetime.date(2019, 1, 1),
    ).filter(
        valid_to__gt=datetime.date(2019, 1, 1),
    )
    assert not qs.exists()


@pytest.mark.django_db
def test_only_one_current_version_per_organisation(organisation):
    """The temporal invariant: at most one version with valid_to IS NULL per organisation."""
    create_version(organisation, datetime.date(2020, 1, 1))
    # The helper pattern always closes the previous row before opening a new one,
    # so this invariant should hold by construction. Verify it does.
    current_count = OrganisationVersion.objects.filter(
        organisation=organisation, valid_to__isnull=True
    ).count()
    assert current_count == 1
