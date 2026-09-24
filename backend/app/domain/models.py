"""SQLAlchemy 2.x ORM models for the QualBot domain.

Entity summary
--------------
Admin              – back-office administrator account (JWT auth target)
Conversation       – a single chat session with a visitor
Message            – one turn inside a Conversation (visitor | bot | system)
Lead               – identified/tracked visitor with qualification state and score
BANTState          – current BANT profile for a Lead (1-to-1, PK = lead_id)
LeadScoreHistory   – append-only log of score changes for a Lead
RoutingAction      – idempotent automated action (alert, booking) linked to a Lead

Relationship map
----------------
Conversation 1 → many Message
Conversation 1 → 0..1 Lead
Lead         1 → 1  BANTState         (PK shared with Lead)
Lead         1 → many LeadScoreHistory
Lead         1 → many RoutingAction

Design notes
------------
* UUID primary keys are generated in Python (str / UUID4) so they are available
  before a flush and work identically on SQLite and PostgreSQL.
* All timestamps are timezone-aware UTC.
* Enum values are stored as strings for readability and portability.  CHECK
  constraints enforce the controlled vocabulary at the database layer.
* Lead.score is the *current* 0-100 score.  LeadScoreHistory records every
  change so the full trajectory is preserved.  No scoring algorithm is
  implemented here — that is a service-layer concern.
* RoutingAction.idempotency_key carries a UNIQUE constraint so that message
  retries cannot create duplicate external actions.
* SQLite foreign-key enforcement requires ``PRAGMA foreign_keys = ON`` which
  the session factory (persistence/database.py) sets via an event listener.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.enums import (
    BANTAuthorityLevel,
    BANTBudgetStatus,
    BANTNeedClarity,
    BANTTimelineUrgency,
    ConversationStatus,
    LeadQualificationStatus,
    RoutingActionStatus,
)

# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------


class Admin(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Back-office administrator account.

    Admins authenticate via JWT to access the analytics dashboard and manage
    conversations.  Passwords are stored as bcrypt hashes — the hashing logic
    lives in the auth service, not here.
    """

    __tablename__ = "admins"
    __table_args__ = (
        UniqueConstraint("email", name="uq_admins_email"),
        {"comment": "Back-office administrator accounts"},
    )

    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Unique admin e-mail address used for JWT login",
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="bcrypt hash of the admin password",
    )
    display_name: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        comment="Human-readable name shown in the dashboard",
    )
    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
        comment="Soft-disable flag; inactive admins cannot authenticate",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Admin id={self.id!r} email={self.email!r}>"


# ---------------------------------------------------------------------------
# Conversation
# ---------------------------------------------------------------------------


class Conversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single chat session between a visitor and QualBot.

    A Conversation may be promoted to a Lead once enough BANT signals are
    collected.  The 1-to-0..1 relationship with Lead is represented by
    Lead.conversation_id FK.
    """

    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'closed', 'abandoned')",
            name="ck_conversations_status",
        ),
        {"comment": "Visitor chat sessions"},
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ConversationStatus.ACTIVE.value,
        comment="ConversationStatus enum value",
    )
    visitor_identifier: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Optional stable visitor fingerprint or session token",
    )
    channel: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="web",
        comment="Source channel, e.g. web, widget",
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="UTC timestamp when the conversation was closed or abandoned",
    )

    # Relationships
    messages: Mapped[list[Message]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
    lead: Mapped[Lead | None] = relationship(
        "Lead",
        back_populates="conversation",
        uselist=False,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Conversation id={self.id!r} status={self.status!r}>"


# ---------------------------------------------------------------------------
# Message
# ---------------------------------------------------------------------------


class Message(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One conversational turn within a Conversation.

    Every visitor, bot, and system message is stored here.  The BANT extraction
    service will annotate messages; routing actions can reference specific
    messages via LeadScoreHistory.message_id.
    """

    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(
            "role IN ('visitor', 'bot', 'system')",
            name="ck_messages_role",
        ),
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
        {"comment": "Individual turns within a Conversation"},
    )

    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        comment="Owning Conversation FK",
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="MessageRole enum value (visitor | bot | system)",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Raw message text",
    )
    token_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Approximate token count for cost tracking",
    )

    # Relationships
    conversation: Mapped[Conversation] = relationship(
        "Conversation",
        back_populates="messages",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Message id={self.id!r} role={self.role!r}>"


# ---------------------------------------------------------------------------
# Lead
# ---------------------------------------------------------------------------


class Lead(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A tracked visitor that has entered the BANT qualification pipeline.

    Lead.score is the *current* 0-100 algorithmic score.  Historical score
    snapshots are stored in LeadScoreHistory; the scoring algorithm itself is
    a domain service concern and is NOT implemented here.

    The 1-to-0..1 relationship with Conversation is modelled as a FK on Lead
    so that a Conversation can exist without a Lead, but every Lead must
    reference exactly one Conversation.
    """

    __tablename__ = "leads"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="ck_leads_score_range"),
        CheckConstraint(
            "qualification_status IN "
            "('new', 'qualifying', 'qualified', 'high_intent', 'not_ready', 'disqualified')",
            name="ck_leads_qualification_status",
        ),
        UniqueConstraint("conversation_id", name="uq_leads_conversation_id"),
        Index(
            "ix_leads_qualification_score",
            "qualification_status",
            "score",
        ),
        {"comment": "Visitor leads under BANT qualification"},
    )

    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Source Conversation FK; each Conversation yields at most one Lead",
    )
    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Visitor e-mail collected during conversation",
    )
    name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Visitor display name",
    )
    company: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Visitor company / organisation",
    )
    score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Current 0-100 algorithmic lead score",
    )
    qualification_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=LeadQualificationStatus.NEW.value,
        index=True,
        comment="LeadQualificationStatus enum value",
    )
    disqualification_reason: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Human-readable reason when status = disqualified",
    )

    # Relationships
    conversation: Mapped[Conversation] = relationship(
        "Conversation",
        back_populates="lead",
    )
    bant_state: Mapped[BANTState] = relationship(
        "BANTState",
        back_populates="lead",
        cascade="all, delete-orphan",
        uselist=False,
    )
    score_history: Mapped[list[LeadScoreHistory]] = relationship(
        "LeadScoreHistory",
        back_populates="lead",
        cascade="all, delete-orphan",
        order_by="LeadScoreHistory.created_at",
    )
    routing_actions: Mapped[list[RoutingAction]] = relationship(
        "RoutingAction",
        back_populates="lead",
        cascade="all, delete-orphan",
        order_by="RoutingAction.created_at",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Lead id={self.id!r} score={self.score!r} "
            f"status={self.qualification_status!r}>"
        )


# ---------------------------------------------------------------------------
# BANTState
# ---------------------------------------------------------------------------


class BANTState(TimestampMixin, Base):
    """Current BANT profile for a Lead (1-to-1, primary key = lead_id).

    This table holds the *live* BANT state updated as the conversation
    progresses.  All four dimensions are stored as string enum values with
    CHECK constraints.  Budget amount uses NUMERIC for exact representation;
    timeline_date stores an optional explicit target date.

    Evidence and confidence columns provide auditability without requiring a
    separate BANT evidence table at this stage.
    """

    __tablename__ = "bant_states"
    __table_args__ = (
        CheckConstraint(
            "budget_status IN ('unknown', 'vague', 'specified', 'none_available')",
            name="ck_bant_states_budget_status",
        ),
        CheckConstraint(
            "authority_level IN ('unknown', 'influencer', 'evaluator', 'decision_maker')",
            name="ck_bant_states_authority_level",
        ),
        CheckConstraint(
            "need_clarity IN ('unknown', 'vague', 'clear', 'specific')",
            name="ck_bant_states_need_clarity",
        ),
        CheckConstraint(
            "timeline_urgency IN ('unknown', 'long_term', 'short_term', 'immediate')",
            name="ck_bant_states_timeline_urgency",
        ),
        CheckConstraint(
            "budget_amount IS NULL OR budget_amount >= 0",
            name="ck_bant_states_budget_nonnegative",
        ),
        CheckConstraint(
            "budget_confidence IS NULL OR "
            "(budget_confidence >= 0.0 AND budget_confidence <= 1.0)",
            name="ck_bant_states_budget_confidence",
        ),
        CheckConstraint(
            "authority_confidence IS NULL OR "
            "(authority_confidence >= 0.0 AND authority_confidence <= 1.0)",
            name="ck_bant_states_authority_confidence",
        ),
        CheckConstraint(
            "need_confidence IS NULL OR "
            "(need_confidence >= 0.0 AND need_confidence <= 1.0)",
            name="ck_bant_states_need_confidence",
        ),
        CheckConstraint(
            "timeline_confidence IS NULL OR "
            "(timeline_confidence >= 0.0 AND timeline_confidence <= 1.0)",
            name="ck_bant_states_timeline_confidence",
        ),
        {"comment": "Live BANT dimension state for a Lead (one row per Lead)"},
    )

    # Shared PK with Lead — avoids a surrogate PK and enforces 1:1 at DB level
    lead_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("leads.id", ondelete="CASCADE"),
        primary_key=True,
        comment="FK to leads.id; also the PK of this table (1:1)",
    )

    # --- Budget ---
    budget_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=BANTBudgetStatus.UNKNOWN.value,
        comment="BANTBudgetStatus enum value",
    )
    budget_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=True,
        comment="Exact stated budget figure; NULL unless status=specified",
    )
    budget_currency: Mapped[str | None] = mapped_column(
        String(3),
        nullable=True,
        comment="ISO-4217 currency code, e.g. USD, INR; NULL unless budget_amount set",
    )
    budget_evidence: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Quoted or paraphrased evidence from the conversation",
    )
    budget_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Confidence score in [0.0, 1.0] for budget extraction",
    )

    # --- Authority ---
    authority_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=BANTAuthorityLevel.UNKNOWN.value,
        comment="BANTAuthorityLevel enum value",
    )
    authority_evidence: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Supporting evidence for authority classification",
    )
    authority_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Confidence score in [0.0, 1.0] for authority extraction",
    )

    # --- Need ---
    need_clarity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=BANTNeedClarity.UNKNOWN.value,
        comment="BANTNeedClarity enum value",
    )
    need_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Free-text summary of the stated need or problem",
    )
    need_evidence: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Supporting evidence for need classification",
    )
    need_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Confidence score in [0.0, 1.0] for need extraction",
    )

    # --- Timeline ---
    timeline_urgency: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=BANTTimelineUrgency.UNKNOWN.value,
        comment="BANTTimelineUrgency enum value",
    )
    timeline_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Explicit target date if the visitor specified one",
    )
    timeline_evidence: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Supporting evidence for timeline classification",
    )
    timeline_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Confidence score in [0.0, 1.0] for timeline extraction",
    )

    # Relationship
    lead: Mapped[Lead] = relationship("Lead", back_populates="bant_state")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<BANTState lead_id={self.lead_id!r} "
            f"B={self.budget_status!r} A={self.authority_level!r} "
            f"N={self.need_clarity!r} T={self.timeline_urgency!r}>"
        )


# ---------------------------------------------------------------------------
# LeadScoreHistory
# ---------------------------------------------------------------------------


class LeadScoreHistory(Base):
    """Immutable append-only record of a Lead's score at a point in time.

    Each row captures a score snapshot.  The scoring algorithm (service layer)
    inserts a row whenever the score changes.  The optional message_id links the
    snapshot to the specific Message that triggered the score update.

    This table is intentionally append-only — rows must never be updated.
    """

    __tablename__ = "lead_score_history"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="ck_lsh_score_range"),
        Index("ix_lsh_lead_created", "lead_id", "created_at"),
        {"comment": "Append-only score snapshot log for Leads"},
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(__import__("uuid").uuid4()),
        comment="UUID4 primary key",
    )
    lead_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        comment="FK to the Lead whose score changed",
    )
    score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Lead score at this point in time (0-100)",
    )
    message_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
        comment="Optional FK to the Message that triggered this score snapshot",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ),
        comment="UTC timestamp when this snapshot was recorded",
    )

    # Relationships
    lead: Mapped[Lead] = relationship("Lead", back_populates="score_history")
    message: Mapped[Message | None] = relationship("Message")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<LeadScoreHistory id={self.id!r} lead_id={self.lead_id!r} score={self.score!r}>"


# ---------------------------------------------------------------------------
# RoutingAction
# ---------------------------------------------------------------------------


class RoutingAction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An idempotent automated action triggered by the qualification engine.

    The ``idempotency_key`` column carries a UNIQUE constraint so that repeated
    processing of the same trigger cannot create duplicate external actions
    (email alerts, calendar bookings).  The key is constructed by the service
    layer from the lead and action type — the exact strategy is a service concern.

    ``status`` tracks whether the external action was attempted/delivered.
    Failed actions can be retried; successful ones must not be re-sent.
    """

    __tablename__ = "routing_actions"
    __table_args__ = (
        CheckConstraint(
            "action_type IN ('continue_chat', 'sales_alert', 'calendar_booking')",
            name="ck_routing_actions_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'success', 'failed')",
            name="ck_routing_actions_status",
        ),
        UniqueConstraint("idempotency_key", name="uq_routing_actions_idempotency_key"),
        Index("ix_routing_actions_lead_id", "lead_id"),
        {"comment": "Idempotent automated actions triggered by the routing engine"},
    )

    lead_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        comment="FK to the Lead that triggered this action",
    )
    action_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="RoutingActionType enum value",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=RoutingActionStatus.PENDING.value,
        comment="RoutingActionStatus enum value",
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Unique key preventing duplicate external actions on retry",
    )
    payload: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="JSON-encoded action payload (recipient, booking URL, etc.)",
    )
    result_detail: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Integration response or error message for audit trail",
    )
    executed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="UTC timestamp when the external action was attempted",
    )

    # Relationships
    lead: Mapped[Lead] = relationship("Lead", back_populates="routing_actions")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<RoutingAction id={self.id!r} type={self.action_type!r} "
            f"status={self.status!r}>"
        )
