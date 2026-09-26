"""
Middleware for serving the API behind a reverse proxy that mounts it under a
path prefix (e.g. Azure API Management at https://api.rcpch.ac.uk/nhs-organisations/v1).

See ``documentation/docs/developer/behind-apim.md`` for the full setup.
"""

import re

from django.urls import get_script_prefix, set_script_prefix

# Conservative allow-list for a URL path prefix: leading slash, then URL-safe
# path characters only. This prevents header injection via X-Forwarded-Prefix.
_PREFIX_RE = re.compile(r"^/[A-Za-z0-9._\-/]*$")


class ForwardedPrefixMiddleware:
    """
    Make Django URL *generation* prefix-aware when the app is served behind a
    reverse proxy that mounts it under a path prefix.

    The proxy must send ``X-Forwarded-Prefix: /nhs-organisations/v1`` on each
    forwarded request. When the header is present the middleware:

    1. Strips the prefix from ``PATH_INFO`` if the proxy forwarded the full
       prefixed path (so the URL resolver still matches the unprefixed routes
       defined in ``urls.py``).
    2. Sets ``SCRIPT_NAME`` to the prefix so that ``reverse()``,
       ``build_absolute_uri()``, the OpenAPI ``servers`` field, hyperlinked
       serializer URLs, pagination links, and the Swagger UI ``specUrl`` all
       include the prefix.
    3. Restores the previous script prefix afterwards so the prefix does not
       leak out of the request (e.g. into management commands run in the same
       process, or into non-proxied requests).

    When the header is absent — direct access to the container app, local dev
    via Caddy, health probes — the middleware is a no-op, so development and
    the raw Azure URL continue to work unchanged.
    """

    header = "HTTP_X_FORWARDED_PREFIX"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        prefix = request.META.get(self.header, "").strip()
        if not prefix:
            return self.get_response(request)

        # Normalise: ensure a leading slash, drop any trailing slash.
        if not prefix.startswith("/"):
            prefix = "/" + prefix
        prefix = prefix.rstrip("/")
        # An empty prefix after normalisation (e.g. "/") means "no prefix".
        if not prefix or not _PREFIX_RE.match(prefix):
            return self.get_response(request)

        # If the proxy forwarded the full prefixed path, strip the prefix so
        # the URL resolver matches the unprefixed routes in urls.py.
        path_info = request.META.get("PATH_INFO", "")
        if path_info.startswith(prefix):
            stripped = path_info[len(prefix):]
            if not stripped.startswith("/"):
                stripped = "/" + stripped
            path_info = stripped
            request.META["PATH_INFO"] = path_info
            request.path_info = path_info

        # Tell Django what to prepend when generating URLs for this request.
        request.META["SCRIPT_NAME"] = prefix
        request.path = prefix + path_info

        # set_script_prefix is thread-local; restore it afterwards so the
        # prefix does not leak beyond this request.
        previous = get_script_prefix()
        set_script_prefix(prefix)
        try:
            return self.get_response(request)
        finally:
            set_script_prefix(previous)
