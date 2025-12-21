from pydantic import BaseModel, Field
from typing import Optional
import time
import uuid

class PrintJobIn(BaseModel):
    printer: str
    raw: str  # ZPL / RAW text

class PrintJob(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    printer: str
    raw: str
    created_at: float = Field(default_factory=lambda: time.time())
    status: str = "queued"  # queued|printing|done|failed
    attempts: int = 0
    last_error: Optional[str] = None
