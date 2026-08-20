"""Small provider helpers; every network call still receives a transport."""

from __future__ import annotations

import json
from typing import Any, Mapping

from mari_components.errors import (
    AuthenticationFailure,
    PermanentFailure,
    RateLimitFailure,
    TransientFailure,
)
from mari_components.http import HttpRequest, HttpResponse, HttpTransport


def send(http: HttpTransport, request: HttpRequest) -> HttpResponse:
    try:
        response = http(request)
    except (TimeoutError, ConnectionError) as error:
        raise TransientFailure("provider request failed") from error
    if response.status in {401, 403}:
        raise AuthenticationFailure(f"provider rejected credentials (HTTP {response.status})")
    if response.status == 429:
        raw = next(
            (value for key, value in response.headers.items() if key.casefold() == "retry-after"), None
        )
        try:
            delay = float(raw) if raw is not None else None
        except ValueError:
            delay = None
        raise RateLimitFailure("provider rate limit exceeded", retry_after=delay)
    if response.status in {408, 425} or response.status >= 500:
        raise TransientFailure(f"provider request failed (HTTP {response.status})")
    if response.status >= 400:
        raise PermanentFailure(f"provider request failed (HTTP {response.status})")
    return response


def json_response(http: HttpTransport, request: HttpRequest) -> Any:
    response = send(http, request)
    try:
        return json.loads(response.body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PermanentFailure("provider returned invalid JSON") from error


def header(headers: Mapping[str, str], name: str) -> str:
    return next((value for key, value in headers.items() if key.casefold() == name.casefold()), "")
