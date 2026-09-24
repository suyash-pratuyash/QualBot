"""Domain layer: enumerations, SQLAlchemy models, and relationship definitions."""

from app.domain.enums import (
    BANTAuthorityLevel,
    BANTBudgetStatus,
    BANTNeedClarity,
    BANTTimelineUrgency,
    ConversationStatus,
    LeadQualificationStatus,
    MessageRole,
    RoutingActionStatus,
    RoutingActionType,
)
from app.domain.models import (
    Admin,
    BANTState,
    Conversation,
    Lead,
    LeadScoreHistory,
    Message,
    RoutingAction,
)

__all__ = [
    # Enums
    "BANTAuthorityLevel",
    "BANTBudgetStatus",
    "BANTNeedClarity",
    "BANTTimelineUrgency",
    "ConversationStatus",
    "LeadQualificationStatus",
    "MessageRole",
    "RoutingActionStatus",
    "RoutingActionType",
    # Models
    "Admin",
    "BANTState",
    "Conversation",
    "Lead",
    "LeadScoreHistory",
    "Message",
    "RoutingAction",
]

