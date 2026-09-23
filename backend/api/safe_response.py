"""Evita que datos persistidos se interpreten como HTML al incrustar JSON."""

from fastapi.responses import JSONResponse


class SafeJSONResponse(JSONResponse):
    def render(self, content):
        body = super().render(content)
        return (body.replace(b'<', b'\\u003c')
                    .replace(b'>', b'\\u003e')
                    .replace(b'&', b'\\u0026'))
