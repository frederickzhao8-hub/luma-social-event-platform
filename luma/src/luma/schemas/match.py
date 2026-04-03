from typing import Literal

from pydantic import BaseModel

from luma.schemas.event import MapEventRead
from luma.schemas.user import UserRead


class ActivateRequest(BaseModel):
    lat: float
    lng: float


class MatchStatusResponse(BaseModel):
    status: Literal["waiting", "matched", "timeout"]
    expires_in: int | None = None          # seconds remaining (waiting only)
    matched_user: UserRead | None = None
    suggested_event: MapEventRead | None = None
