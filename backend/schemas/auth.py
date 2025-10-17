from pydantic import BaseModel


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    access_expires_at: str | None = None
    refresh_expires_at: str | None = None
