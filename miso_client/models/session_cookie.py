"""Browser-session cookie refresh models.

Token values are excluded from ``repr`` so results never leak through logs or
debugger output.
"""

from typing import Optional

from pydantic import BaseModel, Field

from .config import UserInfo


class BrowserSessionRefresh(BaseModel):
    """Renewed browser session returned by Miso ``POST /api/v1/auth/refresh``."""

    access_token: str = Field(..., repr=False, description="New access token")
    expires_in: Optional[int] = Field(default=None, description="Access token lifetime (s)")
    set_cookie: str = Field(
        ..., repr=False, description="Miso Set-Cookie header value to pass to the browser"
    )


class SessionCookieValidation(BaseModel):
    """Outcome of validating a ``miso_access_token`` cookie token, with refresh."""

    valid: bool = Field(..., description="True when the (possibly renewed) token is valid")
    token: Optional[str] = Field(default=None, repr=False, description="Token to use")
    user: Optional[UserInfo] = Field(default=None, description="Validated user")
    set_cookie: Optional[str] = Field(
        default=None,
        repr=False,
        description="Set-Cookie header value the consumer must add to its response",
    )
    refreshed: bool = Field(default=False, description="True when the session was renewed")
