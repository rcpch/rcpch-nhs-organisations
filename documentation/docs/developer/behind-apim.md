# Serving behind Azure API Management

The API is deployed to Azure Container Apps and exposed publicly through an
Azure API Management (APIM) instance using **two APIs**:

| APIM API | URL suffix | Subscription | What it serves |
|---|---|---|---|
| `rcpch-nhs-organisations` (data) | `nhs-organisations/v1` | **Required** | All data endpoints (`/organisations`, `/trusts`, …) |
| `rcpch-nhs-organisations-docs` (docs) | `nhs-organisations/v1/docs` | **Off** | `/`, `/schema`, `/swagger-ui` |

Both APIs point at the same backend (the container app). APIM routes to the
longest matching suffix, so `/nhs-organisations/v1/docs/...` always hits the
docs API and `/nhs-organisations/v1/...` always hits the data API.

| URL | What it is |
|---|---|
| `https://rcpch-nhs-organisations.greenrock-df7c746b.uksouth.azurecontainerapps.io` | The raw container app URL (no prefix, no key). Used for debugging and health probes. |
| `https://api.rcpch.ac.uk/nhs-organisations/v1` | The public data API URL. Requires a subscription key. |
| `https://api.rcpch.ac.uk/nhs-organisations/v1/docs` | The public docs API URL. No key required. |

The Django app itself is mounted at the URL root (see
`rcpch_nhs_organisations/urls.py`), so on the raw container URL the routes are
`/`, `/schema/`, `/swagger-ui/`, `/organisations/`, etc.

## Why two APIs?

APIM's "Subscription required" setting is API-level, not per-operation. With
a single API you cannot require a key on data endpoints while exempting the
docs endpoints — the subscription check runs before operation policies.

Two APIs solve this cleanly: the data API has subscription ON (real key
validation against APIM's subscription database), the docs API has
subscription OFF. No `<check-header>` policy gymnastics, no presence-only
validation trade-off.

## The fix

The fix is in two places: APIM (two APIs + a header) and Django (prefix-aware
URL generation, the OpenAPI `servers` field, and a docs redirect).

### 1. APIM — data API (`nhs-organisations/v1`, subscription ON)

Keep all your existing data operations. Add an API-level inbound policy that
sets the prefix header:

```xml
<policies>
    <inbound>
        <base />
        <set-header name="X-Forwarded-Prefix" exists-action="override">
            <value>/nhs-organisations/v1</value>
        </set-header>
    </inbound>
    <backend>
        <base />
    </backend>
    <outbound>
        <base />
    </outbound>
    <on-error>
        <base />
    </on-error>
</policies>
```

"Subscription required" stays **ON**. APIM validates the key for real on
every data request.

### 2. APIM — docs API (`nhs-organisations/v1/docs`, subscription OFF)

Add three operations, each with a `rewrite-uri` to force the trailing slash
so Django matches first time without a 301 redirect:

| Operation | Per-operation inbound policy |
|---|---|
| `/` | `<rewrite-uri template="/docs/" />` |
| `/schema` | `<rewrite-uri template="/schema/" />` |
| `/swagger-ui` | `<rewrite-uri template="/swagger-ui/" />` |

The `/` operation rewrites to `/docs/` (not `/`) so Django matches the
`docs/` route (the `DocsRedirectView`) rather than the DRF router root at
`""`. Without this, `/docs` would serve the DRF browsable API root instead
of redirecting to GitHub Pages.

API-level inbound policy (note the **docs** prefix value):

```xml
<policies>
    <inbound>
        <base />
        <set-header name="X-Forwarded-Prefix" exists-action="override">
            <value>/nhs-organisations/v1/docs</value>
        </set-header>
    </inbound>
    <backend>
        <base />
    </backend>
    <outbound>
        <base />
    </outbound>
    <on-error>
        <base />
    </on-error>
</policies>
```

"Subscription required" is **OFF** on this API.

### 3. Django — `ForwardedPrefixMiddleware`

`rcpch_nhs_organisations/middleware.py` defines
`ForwardedPrefixMiddleware`, wired in as the outermost middleware in
`settings.py`. When `X-Forwarded-Prefix` is present it:

1. Strips the prefix from `PATH_INFO` if the proxy forwarded the full
   prefixed path (so the URL resolver still matches the unprefixed routes in
   `urls.py`).
2. Sets `SCRIPT_NAME` to the prefix so that `reverse()`,
   `build_absolute_uri()`, hyperlinked serializer URLs, pagination links,
   and the Swagger UI `specUrl` all include the prefix.
3. Restores the previous script prefix afterwards so the prefix does not
   leak out of the request.

The prefix is validated against a conservative allow-list of URL path
characters to prevent header injection.

### 4. Django — OpenAPI `servers` field

`rcpch_nhs_organisations/openapi_hooks.py` defines
`set_servers_to_data_api`, a postprocessing hook that sets the OpenAPI
`servers` field to the **data API** URL when the schema is requested through
APIM.

This is the critical piece for the two-API approach. The spec is served by
the docs API at `/nhs-organisations/v1/docs/schema/`, but the operations live
on the data API at `/nhs-organisations/v1`. Without `servers`, Swagger UI
resolves operation paths relative to the spec URL and "Try it out" hits
`/nhs-organisations/v1/docs/organisations/` → 404. With `servers` set to
`https://api.rcpch.ac.uk/nhs-organisations/v1`, "Try it out" hits the data
API, where the key (entered via the Authorize button) is validated.

The server URL is built from the request's forwarded host plus the
`APIM_DATA_API_PREFIX` setting (default `/nhs-organisations/v1`), so it
tracks the public hostname automatically.

### 5. Django — APIM subscription key in the OpenAPI spec

`add_apim_subscription_key_security` (same file) injects the APIM subscription
key as an OpenAPI security scheme when the schema is requested through APIM.
Swagger UI then shows an **Authorize** button; the consumer enters their key
once and "Try it out" sends `subscription-key` on every request.

Note: `subscription-key` is the header name this APIM instance is configured
to accept (API → Settings → Subscription → Header name). It is **not** the
Azure default (`Ocp-Apim-Subscription-Key`). If the APIM header name is ever
changed back to the default, update `APIM_SUBSCRIPTION_KEY_HEADER` in
`rcpch_nhs_organisations/openapi_hooks.py` to match.

Both hooks are no-ops when `X-Forwarded-Prefix` is absent, so the raw Azure
URL and local dev produce a spec with no security scheme, no `servers`, and no
lock icons.

### 6. Django — docs API base URL redirect

`rcpch_nhs_organisations/hospitals/views/docs_redirect.py` defines
`DocsRedirectView`, mounted at `docs/`. When the request came through APIM
(`X-Forwarded-Prefix` present), it 301-redirects to the project documentation
on GitHub Pages (configurable via `APIM_DOCS_REDIRECT_URL`, default
`https://rcpch.github.io/rcpch-nhs-organisations/`).

Without the header (raw Azure URL, local dev), the view returns 404 so it
does not shadow the normal DRF root at `/`.

### 7. Django — browsable API disabled behind APIM

`rcpch_nhs_organisations/negotiation.py` defines
`APIMAwareContentNegotiation`, wired in as `DEFAULT_CONTENT_NEGOTIATION_CLASS`.
When the request came through APIM (`request._apim_proxied` set by the
middleware), the `BrowsableAPIRenderer` is dropped from the candidate list
so DRF serves JSON only.

The browsable API loads CSS/JS from the unprefixed `/static/` path, which
404s through APIM (no `/static` operation on the docs API), so the page would
render unstyled. Swagger UI (which loads its assets from a CDN) is the
interactive surface through APIM. The browsable API remains available on the
raw Azure URL and in local dev where the header is absent.

## Will this break development?

No. The middleware, both OpenAPI hooks, and the redirect view are all **no-op
when `X-Forwarded-Prefix` is absent**:

- Local dev via Caddy / `./s/dev` — no header, no change.
- Direct access to the container app (the raw Azure URL) — no header, no
  change. `/`, `/schema/`, `/swagger-ui/` continue to work unprefixed, the
  OpenAPI spec has no security scheme and no `servers`, and `/docs/` 404s.
- Health probes — no header, no change.
- `api_comparison.py` against the raw Azure URL — no header, no change.
- Management commands run inside the container — no HTTP request, no
  change.

Tests in `rcpch_nhs_organisations/hospitals/tests/test_forwarded_prefix.py`
cover both the prefixed and unprefixed cases, including that nothing leaks
between requests.

## Security note

`X-Forwarded-Prefix` is a client-controlled header. If a client could reach
the container app directly and send this header, they could make Django
generate URLs with an arbitrary prefix. The middleware validates the prefix
against `^/[A-Za-z0-9._\-/]*$`, which limits the damage to URL generation
(it cannot change routing, since the prefix is only stripped from
`PATH_INFO` when it actually matches). For full hardening, ensure the
container app ingress only accepts traffic from APIM (network isolation /
private endpoint), so untrusted clients cannot inject the header.

## Verifying the fix

After deploying both the APIM config and this code:

```bash
# Docs API — no key needed.
# Swagger UI loads; specUrl points at /nhs-organisations/v1/docs/schema/.
curl -s https://api.rcpch.ac.uk/nhs-organisations/v1/docs/swagger-ui/ | grep -o 'url: "[^"]*schema[^"]*"'

# Spec declares the subscription-key security scheme and servers pointing at the data API.
curl -s https://api.rcpch.ac.uk/nhs-organisations/v1/docs/schema/ | python -m json.tool | grep -A4 -E 'SubscriptionKey|"servers"'

# Docs API base URL redirects to GitHub Pages.
curl -i https://api.rcpch.ac.uk/nhs-organisations/v1/docs/ | grep -i location

# Data API — key required.
curl -i https://api.rcpch.ac.uk/nhs-organisations/v1/integrated_care_boards/ | head -1  # 401
curl -i -H "subscription-key: YOUR_KEY" https://api.rcpch.ac.uk/nhs-organisations/v1/integrated_care_boards/ | head -1  # 200
```

The raw container URL should continue to serve the same pages unprefixed and
with no security scheme in the spec:

```bash
curl https://rcpch-nhs-organisations.greenrock-df7c746b.uksouth.azurecontainerapps.io/schema/
curl https://rcpch-nhs-organisations.greenrock-df7c746b.uksouth.azurecontainerapps.io/swagger-ui/
```