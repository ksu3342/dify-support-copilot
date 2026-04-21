from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Category(str, Enum):
    DEPLOYMENT = "deployment"
    CONFIGURATION = "configuration"
    KNOWLEDGE_BASE = "knowledge-base"
    INTEGRATION = "integration"
    UNCLASSIFIED = "unclassified"


class SlotName(str, Enum):
    DEPLOYMENT_METHOD = "deployment_method"
    VERSION = "version"
    ERROR_MESSAGE = "error_message"
    ENVIRONMENT = "environment"


class RunStatus(str, Enum):
    SCAFFOLDED = "scaffolded"
    ANSWERED = "answered"
    NEEDS_CLARIFICATION = "needs_clarification"
    TICKET_CREATED = "ticket_created"


class TicketStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class SupportSlots(BaseModel):
    deployment_method: Optional[str] = None
    version: Optional[str] = None
    error_message: Optional[str] = None
    environment: Optional[str] = None


class SupportAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    user_id: Optional[str] = Field(default=None, max_length=255)
    follow_up_run_id: Optional[str] = Field(default=None, max_length=255)
    context_slots: SupportSlots = Field(default_factory=SupportSlots)


class Citation(BaseModel):
    chunk_id: Optional[str] = None
    source_url: str
    snapshot_version: str
    title: Optional[str] = None
    chunk_index: Optional[int] = None
    snippet: str


class ClarificationPrompt(BaseModel):
    question: str
    missing_slots: List[SlotName] = Field(default_factory=list)


class RunRecord(BaseModel):
    run_id: str
    question: str
    status: RunStatus
    category: Category
    confidence: float
    created_at: datetime
    updated_at: datetime


class TicketRecord(BaseModel):
    ticket_id: str
    run_id: str
    status: TicketStatus
    summary: str
    created_at: datetime
    updated_at: datetime


class SnapshotRecord(BaseModel):
    snapshot_id: str
    source_url: str
    requested_url: str
    final_url: str
    fetched_at: datetime
    content_hash: str
    snapshot_version: str
    title: Optional[str] = None
    stored_path: Optional[str] = None
    created_at: Optional[datetime] = None


class SupportAskResponse(BaseModel):
    run: RunRecord
    answer: Optional[str] = None
    citations: List[Citation] = Field(default_factory=list)
    clarification: Optional[ClarificationPrompt] = None
    ticket: Optional[TicketRecord] = None
    implemented_capabilities: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    service: str
    app_env: str
    check_type: str
    sqlite_accessible: bool


class ReadinessResponse(BaseModel):
    ready: bool
    snapshot_version: str
    snapshot_count: int
    chunk_count: int
    reasons: List[str] = Field(default_factory=list)
