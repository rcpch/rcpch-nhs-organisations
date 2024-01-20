# Third party imports
from celery import shared_task
from .general_functions import update_organisation_model_with_ORD_changes


@shared_task
def poll_ORD_spineservices_update_organisations_and_trusts():
    """
    polls ORD spineservices API and updates Organisation and Trust objects
    """
    update_organisation_model_with_ORD_changes()
