"""
drf-spectacular postprocessing hooks.

These run after drf-spectacular has built the OpenAPI schema and can mutate
the result before it is served. See the drf-spectacular docs on
``POSTPROCESSING_HOOKS``.
"""

# APIM subscription credentials. This APIM API uses the Azure defaults:
#   * header name:          ``Ocp-Apim-Subscription-Key``
#   * query parameter name: ``subscription-key``
# The OpenAPI security scheme below advertises the header form (which is what
# Swagger UI's "Authorize" button sends on "Try it out"). The query-parameter
# form is still accepted by APIM for consumers who prefer it.
# Exposed as module-level constants so tests and docs can reference them.
APIM_SUBSCRIPTION_KEY_SCHEME = "SubscriptionKey"
APIM_SUBSCRIPTION_KEY_HEADER = "Ocp-Apim-Subscription-Key"


def add_apim_subscription_key_security(result, generator, request, public):
    """
    Inject the Azure API Management subscription key as an OpenAPI security
    scheme so that Swagger UI shows an "Authorize" button and sends the key
    on "Try it out" requests.

    The data endpoints (organisations, trusts, etc.) sit behind APIM and
    require a subscription key. The schema/swagger-ui endpoints do not (they
    are served by a separate docs API with subscription off), but they are
    not part of the OpenAPI spec anyway (``SERVE_INCLUDE_SCHEMA = False``),
    so applying the security requirement globally to the spec's operations is
    correct: every operation in the spec is a data endpoint that needs the
    key.

    The scheme is only injected when the request came through APIM (i.e. the
    ``X-Forwarded-Prefix`` header is present), so the raw Azure URL and local
    dev — which have no key requirement — produce a spec with no security
    scheme and no lock icons in Swagger UI.
    """
    if request is None or "HTTP_X_FORWARDED_PREFIX" not in request.META:
        return result

    components = result.setdefault("components", {})
    security_schemes = components.setdefault("securitySchemes", {})
    # Advertise only the APIM subscription key. drf-spectacular would otherwise
    # also emit cookieAuth/basicAuth schemes derived from DRF's default
    # authenticators; those are irrelevant behind APIM and only confuse the
    # Authorize dialog.
    security_schemes.pop("cookieAuth", None)
    security_schemes.pop("basicAuth", None)
    security_schemes[APIM_SUBSCRIPTION_KEY_SCHEME] = {
        "type": "apiKey",
        "in": "header",
        "name": APIM_SUBSCRIPTION_KEY_HEADER,
        "description": (
            "Azure API Management subscription key. Required for all data "
            "endpoints. Obtain a key from the RCPCH API portal."
        ),
    }
    # Global security requirement — a sensible default for the spec as a whole.
    requirement = [{APIM_SUBSCRIPTION_KEY_SCHEME: []}]
    result["security"] = requirement

    # An operation-level ``security`` overrides the global one, so the global
    # requirement above is not enough on its own. drf-spectacular generates a
    # per-operation ``security`` block from DRF's default authenticators
    # (SessionAuthentication -> cookieAuth, BasicAuthentication -> basicAuth)
    # plus ``{}`` (anonymous, because the viewsets allow unauthenticated
    # access). Swagger UI therefore never attaches the subscription key on
    # "Try it out" and APIM rejects the request with 401. Replace every
    # operation's security with the subscription-key requirement so the key
    # is actually sent.
    for path_item in result.get("paths", {}).values():
        for operation in path_item.values():
            if isinstance(operation, dict) and "responses" in operation:
                operation["security"] = requirement
    return result


def set_servers_to_data_api(result, generator, request, public):
    """
    Set the OpenAPI ``servers`` field to the public data API URL.

    When the schema is served by a separate docs API (subscription off) at
    ``/nhs-organisations/v1/docs/schema/``, Swagger UI resolves the spec's
    (unprefixed) operation paths relative to the spec URL — so "Try it out"
    would hit ``/nhs-organisations/v1/docs/organisations/`` and 404.

    Setting ``servers`` to the data API URL (``/nhs-organisations/v1``) tells
    Swagger UI that the operations live there, so "Try it out" hits the
    key-protected data API regardless of which APIM API served the spec.

    The server URL is built from the request's forwarded host plus the
    ``APIM_DATA_API_PREFIX`` setting (default ``/nhs-organisations/v1``), so
    it tracks the public hostname automatically. Only applied when the request
    came through APIM (``X-Forwarded-Prefix`` present); the raw Azure URL and
    local dev produce a spec with no ``servers`` field (drf-spectacular's
    default), which is correct for those cases.
    """
    if request is None or "HTTP_X_FORWARDED_PREFIX" not in request.META:
        return result

    from django.conf import settings
    from urllib.parse import urlsplit, urlunsplit

    prefix = getattr(settings, "APIM_DATA_API_PREFIX", "/nhs-organisations/v1")
    # build_absolute_uri("/") returns the current request URL with path "/".
    # We keep scheme + host and replace the path with the data API prefix.
    parts = urlsplit(request.build_absolute_uri("/"))
    server_url = urlunsplit((parts.scheme, parts.netloc, prefix, "", ""))
    result["servers"] = [{"url": server_url}]
    return result
