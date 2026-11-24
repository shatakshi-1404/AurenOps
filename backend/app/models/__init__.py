import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import (Boolean, Date, DateTime, ForeignKey, Index, Integer, LargeBinary,
                        Numeric, String, Text, UniqueConstraint)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, deferred, mapped_column

from app.core.config import settings
from app.core.db import Base


def utcnow():
    return datetime.now(timezone.utc)


def pk():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def fk(table, nullable=False, ondelete="CASCADE"):
    return mapped_column(UUID(as_uuid=True), ForeignKey(f"{table}.id", ondelete=ondelete), nullable=nullable, index=True)


def created():
    return mapped_column(DateTime(timezone=True), default=utcnow, index=True)


def ts(nullable=True):
    return mapped_column(DateTime(timezone=True), nullable=nullable)


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[uuid.UUID] = pk()
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = created()


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = pk()
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(300))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = created()


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("org_id", "user_id"),)
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = fk("organizations")
    user_id: Mapped[uuid.UUID] = fk("users")
    role: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = created()


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (UniqueConstraint("org_id", "key"),)
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = fk("organizations")
    key: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = fk("organizations")
    user_id: Mapped[uuid.UUID] = fk("users")
    agent_id: Mapped[uuid.UUID | None] = fk("agents", nullable=True, ondelete="SET NULL")
    request: Mapped[str] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="QUEUED", index=True)
    plan: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_usage: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = created()
    started_at: Mapped[datetime | None] = ts()
    finished_at: Mapped[datetime | None] = ts()


class WorkflowNode(Base):
    __tablename__ = "workflow_nodes"
    __table_args__ = (UniqueConstraint("run_id", "node_key"),)
    id: Mapped[uuid.UUID] = pk()
    run_id: Mapped[uuid.UUID] = fk("agent_runs")
    org_id: Mapped[uuid.UUID] = fk("organizations")
    node_key: Mapped[str] = mapped_column(String(60))
    agent_key: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(30), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    input: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = ts()
    finished_at: Mapped[datetime | None] = ts()
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class WorkflowEvent(Base):
    __tablename__ = "workflow_events"
    __table_args__ = (Index("ix_events_run_created", "run_id", "created_at"),)
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = fk("organizations")
    run_id: Mapped[uuid.UUID] = fk("agent_runs")
    event: Mapped[str] = mapped_column(String(60), index=True)
    node_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = created()


class Tool(Base):
    __tablename__ = "tools"
    __table_args__ = (UniqueConstraint("org_id", "name"),)
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = fk("organizations")
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text, default="")
    min_role: Mapped[str] = mapped_column(String(20), default="viewer")
    side_effect: Mapped[bool] = mapped_column(Boolean, default=False)
    policy_action: Mapped[str | None] = mapped_column(String(60), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Integration(Base):
    __tablename__ = "integrations"
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = fk("organizations")
    kind: Mapped[str] = mapped_column(String(30))  # crm | email | database | storage
    name: Mapped[str] = mapped_column(String(120))
    provider: Mapped[str] = mapped_column(String(60), default="mock")
    status: Mapped[str] = mapped_column(String(20), default="connected")
    config_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_health_at: Mapped[datetime | None] = ts()
    last_rotated_at: Mapped[datetime | None] = ts()
    created_at: Mapped[datetime] = created()


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = fk("organizations")
    filename: Mapped[str] = mapped_column(String(300))
    content_type: Mapped[str] = mapped_column(String(100), default="")
    category: Mapped[str] = mapped_column(String(60), default="general")
    status: Mapped[str] = mapped_column(String(20), default="processing")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_roles: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # None = all roles
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_by: Mapped[uuid.UUID | None] = fk("users", nullable=True, ondelete="SET NULL")
    raw: Mapped[bytes | None] = deferred(mapped_column(LargeBinary, nullable=True))
    created_at: Mapped[datetime] = created()


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (Index("ix_chunks_emb", "embedding", postgresql_using="hnsw",
                            postgresql_ops={"embedding": "vector_cosine_ops"}),)
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = fk("organizations")
    document_id: Mapped[uuid.UUID] = fk("documents")
    idx: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    embedding: Mapped[list] = mapped_column(Vector(settings.embedding_dim))


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = fk("organizations")
    name: Mapped[str] = mapped_column(String(200))
    company: Mapped[str] = mapped_column(String(200), default="")
    email: Mapped[str] = mapped_column(String(320))
    tier: Mapped[str] = mapped_column(String(20), default="standard")
    created_at: Mapped[datetime] = created()


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (Index("ix_invoices_org_status_due", "org_id", "status", "due_date"),)
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = fk("organizations")
    customer_id: Mapped[uuid.UUID] = fk("customers")
    number: Mapped[str] = mapped_column(String(40))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    issued_at: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date)
    paid_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|overdue|paid|void
    reminders_sent: Mapped[int] = mapped_column(Integer, default=0)
    last_reminder_at: Mapped[date | None] = mapped_column(Date, nullable=True)


class EmailDraft(Base):
    __tablename__ = "email_drafts"
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = fk("organizations")
    run_id: Mapped[uuid.UUID | None] = fk("agent_runs", nullable=True, ondelete="SET NULL")
    customer_id: Mapped[uuid.UUID] = fk("customers")
    invoice_id: Mapped[uuid.UUID] = fk("invoices")
    to_email: Mapped[str] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    original_subject: Mapped[str] = mapped_column(String(300), default="")
    original_body: Mapped[str] = mapped_column(Text, default="")
    edited: Mapped[bool] = mapped_column(Boolean, default=False)
    # draft | approved | rejected | sending | sent | failed
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = ts()
    created_at: Mapped[datetime] = created()


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = fk("organizations")
    run_id: Mapped[uuid.UUID] = fk("agent_runs")
    action: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(300))
    reason: Mapped[str] = mapped_column(Text, default="")
    agent_key: Mapped[str] = mapped_column(String(60), default="communication_agent")
    policy: Mapped[str] = mapped_column(String(120), default="")
    risk: Mapped[str] = mapped_column(String(20), default="medium")
    # pending | approved | rejected | expired | invalidated
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    payload_hash: Mapped[str] = mapped_column(String(64))
    approved_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    approved_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decided_by: Mapped[uuid.UUID | None] = fk("users", nullable=True, ondelete="SET NULL")
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = ts()
    expires_at: Mapped[datetime | None] = ts()
    created_at: Mapped[datetime] = created()


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = fk("organizations")
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    resource_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = created()


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = fk("organizations")
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    link: Mapped[str | None] = mapped_column(String(200), nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = created()


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = fk("organizations")
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(40), default="collection")
    summary: Mapped[dict] = mapped_column(JSONB, default=dict)
    csv: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = created()
