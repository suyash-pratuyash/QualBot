"""Domain enumerations for QualBot.

All enums are string-backed so their values are stored as readable strings in both
SQLite and PostgreSQL; they are also validated at the application layer before reaching
the database.  Each member's value is the literal string written to the DB column.
"""

from __future__ import annotations

from enum import StrEnum


class ConversationStatus(StrEnum):
    """Lifecycle state of a Conversation session."""

    ACTIVE = "active"
    CLOSED = "closed"
    ABANDONED = "abandoned"


class MessageRole(StrEnum):
    """Who produced a Message within a Conversation."""

    VISITOR = "visitor"
    BOT = "bot"
    SYSTEM = "system"


class LeadQualificationStatus(StrEnum):
    """BANT-driven qualification state of a Lead.

    Progression is:  NEW → QUALIFYING → QUALIFIED | HIGH_INTENT | NOT_READY | DISQUALIFIED
    Transitions are enforced by the domain service layer, not the DB.
    """

    NEW = "new"
    QUALIFYING = "qualifying"
    QUALIFIED = "qualified"
    HIGH_INTENT = "high_intent"
    NOT_READY = "not_ready"
    DISQUALIFIED = "disqualified"


# ---------------------------------------------------------------------------
# BANT dimension enums
# ---------------------------------------------------------------------------


class BANTBudgetStatus(StrEnum):
    """Observed budget dimension status extracted from conversation."""

    UNKNOWN = "unknown"
    VAGUE = "vague"
    SPECIFIED = "specified"
    NONE_AVAILABLE = "none_available"


class BANTAuthorityLevel(StrEnum):
    """Decision-making authority level of the visitor."""

    UNKNOWN = "unknown"
    INFLUENCER = "influencer"
    EVALUATOR = "evaluator"
    DECISION_MAKER = "decision_maker"


class BANTNeedClarity(StrEnum):
    """Clarity of the visitor's stated need or problem."""

    UNKNOWN = "unknown"
    VAGUE = "vague"
    CLEAR = "clear"
    SPECIFIC = "specific"


class BANTTimelineUrgency(StrEnum):
    """Purchase/adoption timeline extracted from conversation."""

    UNKNOWN = "unknown"
    LONG_TERM = "long_term"
    SHORT_TERM = "short_term"
    IMMEDIATE = "immediate"


# ---------------------------------------------------------------------------
# Routing / action enums
# ---------------------------------------------------------------------------


class RoutingActionType(StrEnum):
    """Type of automated action triggered by the routing engine."""

    CONTINUE_CHAT = "continue_chat"
    SALES_ALERT = "sales_alert"
    CALENDAR_BOOKING = "calendar_booking"


class RoutingActionStatus(StrEnum):
    """Execution / delivery status of a RoutingAction."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
