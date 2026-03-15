from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SessionInfo(BaseModel):
    session_id: UUID
    name: str
    message_count: int
    created_at: datetime
