"""Requests and responses, independent of the server that carries them.

The application (app.py) maps a `Request` to a `Response`; server.py adapts
them to http.server. Keeping the two apart lets the tests call the application
directly, and lets the server be replaced without touching any page.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from http.cookies import CookieError, SimpleCookie
from urllib.parse import parse_qs, quote, unquote, urlsplit

HTML = "text/html; charset=utf-8"
TEXT = "text/plain; charset=utf-8"
MAX_FORM_FIELDS = 20

Headers = tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Request:
    method: str
    path: str  # the URL path, percent-decoded
    cookies: Mapping[str, str] = field(default_factory=dict)
    form: Mapping[str, str] = field(default_factory=dict)  # an urlencoded POST body

    @classmethod
    def parse(cls, method: str, target: str, cookie: str | None = None,
              body: bytes = b"") -> Request:
        """A request from its method, request target, Cookie header and body."""
        return cls(method.upper(), unquote(urlsplit(target).path), _cookies(cookie),
                   _form(body))


@dataclass(frozen=True)
class Response:
    status: int
    body: bytes = b""
    content_type: str = TEXT
    headers: Headers = ()

    def header(self, name: str) -> str | None:
        return next((value for key, value in self.headers if key.lower() == name.lower()), None)


def html_response(text: str, status: int = 200) -> Response:
    return Response(status, text.encode("utf-8"), HTML)


def redirect(path: str, status: int = 303, headers: Headers = ()) -> Response:
    """Redirect to a path of this site (percent-encoded here, so any path is safe)."""
    return Response(status, headers=(("Location", quote(path)), *headers))


def local_path(value: str | None, fallback: str = "/") -> str:
    """A path on this site, or the fallback; never another site (no open redirect)."""
    if not value or not value.startswith("/") or value.startswith("//") or "\\" in value:
        return fallback
    return value


def set_cookie(name: str, value: str, max_age: int) -> tuple[str, str]:
    return ("Set-Cookie", f"{name}={value}; Path=/; Max-Age={max_age}; SameSite=Lax")


def _cookies(header: str | None) -> dict[str, str]:
    if not header:
        return {}
    jar: SimpleCookie = SimpleCookie()
    try:
        jar.load(header)
    except CookieError:
        return {}
    return {name: morsel.value for name, morsel in jar.items()}


def _form(body: bytes) -> dict[str, str]:
    if not body:
        return {}
    try:
        fields = parse_qs(body.decode("utf-8"), max_num_fields=MAX_FORM_FIELDS)
    except (UnicodeDecodeError, ValueError):
        return {}
    return {name: values[0] for name, values in fields.items()}
