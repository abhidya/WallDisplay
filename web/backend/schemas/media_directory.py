from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class MediaDirectoryBase(BaseModel):
    name: str
    path: str
    category: str = "background"
    enabled: bool = True
    scan_mode: str = "recursive"


class MediaDirectoryCreate(MediaDirectoryBase):
    pass


class MediaDirectoryUpdate(BaseModel):
    name: Optional[str] = None
    path: Optional[str] = None
    category: Optional[str] = None
    enabled: Optional[bool] = None
    scan_mode: Optional[str] = None


class MediaDirectoryResponse(MediaDirectoryBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
