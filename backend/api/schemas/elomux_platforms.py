from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl

from api.schemas.safe_input import SafeInputModel


class ElomuxPlatformCreate(SafeInputModel):
    name: str = Field(min_length=1, max_length=120)
    url: HttpUrl
    is_active: bool = True


class ElomuxPlatformUpdate(SafeInputModel):
    non_nullable_update_fields = frozenset({'name', 'url', 'is_active'})

    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    url: Optional[HttpUrl] = None
    is_active: Optional[bool] = None


class ElomuxPlatformResponse(BaseModel):
    id: int
    name: str
    url: str
    is_active: bool
    created_at: datetime
    updated_at: datetime\n
