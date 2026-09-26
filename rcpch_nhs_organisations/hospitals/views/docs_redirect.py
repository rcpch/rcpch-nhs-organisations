"""
A redirect view for the docs API base URL.

When the API is served behind Azure API Management with a separate docs API
(see ``documentation/docs/developer/behind-apim.md``), the docs API's base
URL (``https://api.rcpch.ac.uk/nhs-organisations/v1/docs/``) is a natural
landing point for a consumer. Rather than serve the DRF browsable API root
there (which would 401 on every link click through the key-protected data
API), we redirect to the project's documentation on GitHub Pages.

The redirect target is configurable via the ``APIM_DOCS_REDIRECT_URL`` setting
(default: the RCPCH NHS Organisations GitHub Pages site). When the request
did not come through APIM (no ``X-Forwarded-Prefix`` header), the view returns
404 so it does not shadow the normal DRF root on the raw Azure URL / local dev.
"""

from django.conf import settings
from django.http import HttpResponsePermanentRedirect
from django.views import View

DEFAULT_DOCS_REDIRECT_URL = "https://rcpch.github.io/rcpch-nhs-organisations/"


class DocsRedirectView(View):
    """
    Redirect the docs API base URL to the project documentation.

    Mounted at ``docs/`` on the URLconf. Only active when the request came
    through APIM (``X-Forwarded-Prefix`` present); otherwise returns 404 so
    the normal DRF root at ``/`` is unaffected on the raw Azure URL and in
    local dev.
    """

    def get(self, request, *args, **kwargs):
        if "HTTP_X_FORWARDED_PREFIX" not in request.META:
            # Not behind APIM — don't shadow the DRF root.
            from django.http import Http404

            raise Http404("Docs redirect is only active behind APIM.")

        url = getattr(
            settings, "APIM_DOCS_REDIRECT_URL", DEFAULT_DOCS_REDIRECT_URL
        )
        return HttpResponsePermanentRedirect(url)