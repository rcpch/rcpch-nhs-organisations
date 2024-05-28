"""
WSGI config for rcpch_nhs_organisations project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.1/howto/deployment/wsgi/
"""

import os
import sys

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rcpch_nhs_organisations.settings")

application = get_wsgi_application()
