"""
drf-spectacular postprocessing hooks.

These run after drf-spectacular has built the OpenAPI schema and can mutate
the result before it is served. See the drf-spectacular docs on
``POSTPROCESSING_HOOKS``.
"""

# The APIM subscription key, sent in the ``Ocp-Apim-Subscription-Key`` header.
# Exposed as a scheme name constant so tests and docs can reference it.
APIM_SUBSCRIPTION_KEY_SCHEME = "OcpApimSubscriptionKey"
APIM_SUBSCRIPTION_KEY_HEADER = "Ocp-Apim-Subscription-Key"


def add_apim_subscription_key_security(result, generator, request, public):
    """
    Inject the Azure API Management subscription key as an OpenAPI security
    scheme so that Swagger UI shows an "Authorize" button and sends the key
    on "Try it out" requests.

    The data endpoints (organisations, trusts, etc.) sit behind APIM and
    require a subscription key. The schema/swagger-ui endpoints do not (they
    are exempted on the APIM side), but they are not part of the OpenAPI spec
    anyway (``SERVE_INCLUDE_SCHEMA = False``), so applying the security
    requirement globally to the spec's operations is correct: every
    operation in the spec is a data endpoint that needs the key.

    The scheme is only injected when the request came through APIM (i.e. the
    ``X-Forwarded-Prefix`` header is present), so the raw Azure URL and local
    dev — which have no key requirement — produce a spec with no security
    scheme and no lock icons in Swagger UI.
    """
    if request is None or "HTTP_X_FORWARDED_PREFIX" not in request.META:
        return result

    components = result.setdefault("components", {})
    security_schemes = components.setdefault("securitySchemes", {})
    security_schemes[APIM_SUBSCRIPTION_KEY_SCHEME] = {
        "type": "apiKey",
        "in": "header",
        "name": APIM_SUBSCRIPTION_KEY_HEADER,
        "description": (
            "Azure API Management subscription key. Required for all data "
            "endpoints. Obtain a key from the RCPCH API portal."
        ),
    }
    # Global security requirement — applies to every operation in the spec.
    result["security"] = [{APIM_SUBSCRIPTION_KEY_SCHEME: []}]
    return result
