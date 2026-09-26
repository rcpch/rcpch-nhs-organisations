"""
DRF content negotiation that drops the browsable API renderer when the
request came through APIM.

The browsable API serves HTML with CSS/JS from the unprefixed ``/static/``
path, which 404s through APIM (no ``/static`` operation on the docs API), so
the page renders unstyled. When the request is flagged as APIM-proxied
(``request._apim_proxied`` set by ``ForwardedPrefixMiddleware``), the
browsable renderer is dropped from the candidate list and DRF falls back to
``JSONRenderer``. The browsable API remains available on the raw Azure URL
and in local dev where the header is absent.
"""

from rest_framework.negotiation import DefaultContentNegotiation


class APIMAwareContentNegotiation(DefaultContentNegotiation):
    """
    Default DRF content negotiation, but the browsable API renderer is removed
    from the candidate list when the request came through APIM.
    """

    def select_renderer(self, request, renderers, format_suffix=None):
        if getattr(request, "_apim_proxied", False):
            renderers = [
                r
                for r in renderers
                if "BrowsableAPIRenderer" not in r.__class__.__name__
            ]
        return super().select_renderer(request, renderers, format_suffix)