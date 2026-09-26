"""
Tests for ForwardedPrefixMiddleware.

The middleware makes Django URL *generation* prefix-aware when the app is
served behind a reverse proxy (Azure API Management) that mounts it under a
path prefix. The proxy signals the prefix with an ``X-Forwarded-Prefix``
header. When the header is absent the middleware is a no-op, so direct
access to the container app and local dev are unaffected.

The DRF DefaultRouter API root (``/``) is the clearest signal: its links are
built with ``reverse()`` + ``build_absolute_uri()``, so they pick up the
script prefix. The Swagger UI page embeds a ``specUrl`` built with
``reverse("schema")``, which also picks up the prefix.

These tests do not require PostGIS — they only exercise URL routing and
generation through the DRF schema/root endpoints.
"""

import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


# -----------------------------------------------------------------------------
# No header -> no-op (the raw Azure URL / local dev case)
# -----------------------------------------------------------------------------


def test_api_root_unprefixed_without_header(api_client):
    """Without the header, reversed URLs in the API root are unprefixed."""
    response = api_client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert "trusts" in body
    assert "/nhs-organisations/v1" not in body["trusts"]


def test_schema_unprefixed_without_header(api_client):
    """Without the header, /schema/ resolves and paths are unprefixed."""
    response = api_client.get("/schema/")
    assert response.status_code == 200
    paths = response.json().get("paths", {})
    assert paths, "expected drf-spectacular to emit paths"
    for path in paths:
        assert "/nhs-organisations/v1" not in path


def test_swagger_ui_unprefixed_without_header(api_client):
    """Without the header, the Swagger UI specUrl is unprefixed."""
    response = api_client.get("/swagger-ui/")
    assert response.status_code == 200
    # The spec URL is embedded as a JS string; the only "/schema/" reference
    # should not contain the prefix.
    assert b"organisations/v1/schema/" not in response.content


# -----------------------------------------------------------------------------
# Header present, proxy already stripped the prefix (recommended APIM setup)
# -----------------------------------------------------------------------------


def test_api_root_prefixed_when_header_sent(api_client):
    """With X-Forwarded-Prefix, reversed URLs in the API root include the prefix."""
    response = api_client.get(
        "/",
        HTTP_X_FORWARDED_PREFIX="/nhs-organisations/v1",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["trusts"].endswith("/nhs-organisations/v1/trusts/")
    assert body["organisations"].endswith("/nhs-organisations/v1/organisations/")


def test_swagger_ui_html_contains_prefixed_spec_url(api_client):
    """The Swagger UI page embeds a specUrl that includes the prefix.

    drf-spectacular escapes the spec URL for JS context (the hyphen renders
    as \\u002D), so we match on a substring that does not include the hyphen.
    """
    response = api_client.get(
        "/swagger-ui/",
        HTTP_X_FORWARDED_PREFIX="/nhs-organisations/v1",
    )
    assert response.status_code == 200
    assert b"organisations/v1/schema/" in response.content


def test_schema_still_resolves_with_header(api_client):
    """With the header, /schema/ still resolves (paths stay unprefixed by design)."""
    response = api_client.get(
        "/schema/",
        HTTP_X_FORWARDED_PREFIX="/nhs-organisations/v1",
    )
    assert response.status_code == 200
    # drf-spectacular builds `paths` from URL patterns, not reverse(), so they
    # remain unprefixed. Swagger UI resolves them relative to the (prefixed)
    # spec URL, so this is the intended behaviour.
    paths = response.json().get("paths", {})
    assert "/organisations/" in paths


# -----------------------------------------------------------------------------
# Header present, proxy forwarded the FULL prefixed path (defensive strip)
# -----------------------------------------------------------------------------


def test_strips_prefix_when_proxy_forwarded_full_path(api_client):
    """
    If the proxy forwards the full prefixed path (no rewrite), the middleware
    strips the prefix so the unprefixed routes still match, and generated URLs
    still include the prefix.
    """
    response = api_client.get(
        "/nhs-organisations/v1/",
        HTTP_X_FORWARDED_PREFIX="/nhs-organisations/v1",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["trusts"].endswith("/nhs-organisations/v1/trusts/")


def test_strips_prefix_for_schema_full_path(api_client):
    response = api_client.get(
        "/nhs-organisations/v1/schema/",
        HTTP_X_FORWARDED_PREFIX="/nhs-organisations/v1",
    )
    assert response.status_code == 200


def test_strips_prefix_for_swagger_ui_full_path(api_client):
    response = api_client.get(
        "/nhs-organisations/v1/swagger-ui/",
        HTTP_X_FORWARDED_PREFIX="/nhs-organisations/v1",
    )
    assert response.status_code == 200
    assert b"organisations/v1/schema/" in response.content


# -----------------------------------------------------------------------------
# Header validation / normalisation
# -----------------------------------------------------------------------------


def test_invalid_prefix_header_is_ignored(api_client):
    """A prefix with non-path characters is rejected and the request is unprefixed."""
    response = api_client.get(
        "/",
        HTTP_X_FORWARDED_PREFIX="//ev il",
    )
    assert response.status_code == 200
    body = response.json()
    assert "/nhs-organisations/v1" not in body["trusts"]


def test_prefix_without_leading_slash_is_normalised(api_client):
    """A prefix supplied without a leading slash is normalised and applied."""
    response = api_client.get(
        "/",
        HTTP_X_FORWARDED_PREFIX="nhs-organisations/v1",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["trusts"].endswith("/nhs-organisations/v1/trusts/")


def test_trailing_slash_prefix_is_normalised(api_client):
    """A trailing slash on the prefix is stripped (no double slash in URLs)."""
    response = api_client.get(
        "/",
        HTTP_X_FORWARDED_PREFIX="/nhs-organisations/v1/",
    )
    assert response.status_code == 200
    body = response.json()
    # Normalised prefix has no trailing slash, so the URL should not contain "//"
    # after the host.
    assert body["trusts"].endswith("/nhs-organisations/v1/trusts/")
    assert "//trusts/" not in body["trusts"]


# -----------------------------------------------------------------------------
# Script prefix does not leak between requests
# -----------------------------------------------------------------------------


def test_prefix_does_not_leak_between_requests(api_client):
    """A proxied request must not leave the prefix set for the next request."""
    api_client.get(
        "/",
        HTTP_X_FORWARDED_PREFIX="/nhs-organisations/v1",
    )
    response = api_client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert "/nhs-organisations/v1" not in body["trusts"]


def test_prefix_change_between_requests(api_client):
    """Two different prefixes in sequence are each applied independently."""
    r1 = api_client.get("/", HTTP_X_FORWARDED_PREFIX="/foo/v1")
    assert r1.json()["trusts"].endswith("/foo/v1/trusts/")
    r2 = api_client.get("/", HTTP_X_FORWARDED_PREFIX="/bar/v2")
    assert r2.json()["trusts"].endswith("/bar/v2/trusts/")
    r3 = api_client.get("/")
    assert "/foo/v1" not in r3.json()["trusts"]
    assert "/bar/v2" not in r3.json()["trusts"]


# -----------------------------------------------------------------------------
# OpenAPI security scheme (APIM subscription key)
# -----------------------------------------------------------------------------


def test_schema_has_no_security_scheme_without_header(api_client):
    """Without the APIM header, the spec has no subscription-key security scheme."""
    response = api_client.get("/schema/")
    assert response.status_code == 200
    schema = response.json()
    security_schemes = schema.get("components", {}).get("securitySchemes", {})
    assert "OcpApimSubscriptionKey" not in security_schemes
    assert "security" not in schema or schema["security"] == []


def test_schema_has_apim_security_scheme_with_header(api_client):
    """Through APIM, the spec declares the subscription-key security scheme."""
    response = api_client.get(
        "/schema/",
        HTTP_X_FORWARDED_PREFIX="/nhs-organisations/v1",
    )
    assert response.status_code == 200
    schema = response.json()
    schemes = schema.get("components", {}).get("securitySchemes", {})
    assert "OcpApimSubscriptionKey" in schemes
    scheme = schemes["OcpApimSubscriptionKey"]
    assert scheme["type"] == "apiKey"
    assert scheme["in"] == "header"
    assert scheme["name"] == "Ocp-Apim-Subscription-Key"
    # Global security requirement is set.
    assert schema.get("security") == [{"OcpApimSubscriptionKey": []}]


def test_security_scheme_does_not_leak_between_requests(api_client):
    """A proxied schema request must not leave the security scheme on the next."""
    api_client.get(
        "/schema/",
        HTTP_X_FORWARDED_PREFIX="/nhs-organisations/v1",
    )
    response = api_client.get("/schema/")
    schema = response.json()
    assert "OcpApimSubscriptionKey" not in schema.get("components", {}).get(
        "securitySchemes", {}
    )


# -----------------------------------------------------------------------------
# OpenAPI servers field (points Swagger UI "Try it out" at the data API)
# -----------------------------------------------------------------------------


def test_schema_has_no_servers_without_header(api_client):
    """Without the APIM header, the spec has no servers field (drf-spectacular default)."""
    response = api_client.get("/schema/")
    assert response.status_code == 200
    schema = response.json()
    # drf-spectacular emits no servers by default.
    assert not schema.get("servers")


def test_schema_servers_points_at_data_api_with_header(api_client, settings):
    """Through APIM, servers[0].url is the data API prefix on the forwarded host."""
    settings.ALLOWED_HOSTS = ["*"]
    response = api_client.get(
        "/schema/",
        HTTP_X_FORWARDED_PREFIX="/nhs-organisations/v1/docs",
        HTTP_X_FORWARDED_HOST="api.rcpch.ac.uk",
        HTTP_X_FORWARDED_PROTO="https",
    )
    assert response.status_code == 200
    schema = response.json()
    servers = schema.get("servers", [])
    assert servers, "expected a servers entry"
    # The server URL must point at the data API prefix, NOT the docs prefix.
    assert servers[0]["url"] == "https://api.rcpch.ac.uk/nhs-organisations/v1"
    assert "/docs" not in servers[0]["url"]


def test_servers_does_not_leak_between_requests(api_client, settings):
    """A proxied schema request must not leave servers set on the next."""
    settings.ALLOWED_HOSTS = ["*"]
    api_client.get(
        "/schema/",
        HTTP_X_FORWARDED_PREFIX="/nhs-organisations/v1/docs",
        HTTP_X_FORWARDED_HOST="api.rcpch.ac.uk",
        HTTP_X_FORWARDED_PROTO="https",
    )
    response = api_client.get("/schema/")
    schema = response.json()
    assert not schema.get("servers")


# -----------------------------------------------------------------------------
# Docs API base URL redirect
# -----------------------------------------------------------------------------


def test_docs_redirect_404_without_header(api_client):
    """Without the APIM header, /docs/ 404s so it doesn't shadow the DRF root."""
    response = api_client.get("/docs/")
    assert response.status_code == 404


def test_docs_redirects_to_github_pages_with_header(api_client):
    """Through APIM, /docs/ 301-redirects to the GitHub Pages docs site."""
    response = api_client.get(
        "/docs/",
        HTTP_X_FORWARDED_PREFIX="/nhs-organisations/v1/docs",
    )
    assert response.status_code == 301
    assert response["Location"] == "https://rcpch.github.io/rcpch-nhs-organisations/"


def test_docs_redirect_uses_setting(api_client, settings):
    """The redirect target is configurable via APIM_DOCS_REDIRECT_URL."""
    settings.APIM_DOCS_REDIRECT_URL = "https://example.com/docs/"
    response = api_client.get(
        "/docs/",
        HTTP_X_FORWARDED_PREFIX="/nhs-organisations/v1/docs",
    )
    assert response.status_code == 301
    assert response["Location"] == "https://example.com/docs/"
