# python / django imports
from django.contrib.auth.models import User, Group
from rest_framework import viewsets
from rest_framework import permissions

from pprint import pprint

# local imports
from rcpch_nhs_organisations.hospitals.models import Organisation, Service
from rcpch_nhs_organisations.hospitals.serializers import (
    UserSerializer,
    GroupSerializer,
    OrganisationODSSerializer,
)

from .general_functions import all_nhs_hospitals_list


# def deserialize(instance):
#     final_object = []
#     organisation_field_list = [field.name for field in Organisation._meta.get_fields()]
#     organisation = Organisation()
#     for key in instance:
#         if key in organisation_field_list:
#             setattr(organisation, key, instance.get(key))
#     organisation.save()


class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """

    all_hospitals = all_nhs_hospitals_list()
    print(all_hospitals)

    # for hospital in all_hospitals:
    #     services = deserialize(instance=hospital)

    queryset = User.objects.all().order_by("-date_joined")
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]


class GroupViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """

    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticated]


class OrganisationODSViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """

    queryset = Organisation.objects.all()
    serializer_class = OrganisationODSSerializer
    permission_classes = [permissions.IsAuthenticated]
