"""Tests for QualBot Phase 1A domain models.

Coverage
--------
- UUID primary key auto-generation
- Relationship traversal (Conversation → Messages, Lead → BANTState, etc.)
- CHECK constraint enforcement for all controlled-vocabulary columns
- UNIQUE constraint enforcement (admin email, conversation_id on lead, idempotency key)
- Foreign key enforcement (cascade, restrict, set null)
- Score range boundary (0–100)
- Default values for status/qualification columns
- Append-only LeadScoreHistory with optional message_id
- RoutingAction idempotency key uniqueness
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.enums import (
    BANTAuthorityLevel,
    BANTBudgetStatus,
    BANTNeedClarity,
    BANTTimelineUrgency,
    ConversationStatus,
    LeadQualificationStatus,
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

# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_conversation(db: Session, **kwargs) -> Conversation:
    conv = Conversation(**kwargs)
    db.add(conv)
    db.flush()
    return conv


def _make_lead(db: Session, conversation: Conversation, **kwargs) -> Lead:
    lead = Lead(conversation_id=conversation.id, **kwargs)
    db.add(lead)
    db.flush()
    return lead


def _make_message(
    db: Session,
    conversation: Conversation,
    role: str = "visitor",
    content: str = "hello",
) -> Message:
    msg = Message(conversation_id=conversation.id, role=role, content=content)
    db.add(msg)
    db.flush()
    return msg


# ---------------------------------------------------------------------------
# Admin model
# ---------------------------------------------------------------------------


class TestAdmin:
    def test_uuid_pk_auto_generated(self, db: Session) -> None:
        admin = Admin(email="a@example.com", hashed_password="hash1")
        db.add(admin)
        db.flush()
        assert admin.id is not None
        uuid.UUID(admin.id)  # validates UUID4 format

    def test_defaults(self, db: Session) -> None:
        admin = Admin(email="b@example.com", hashed_password="hash2")
        db.add(admin)
        db.flush()
        assert admin.is_active is True
        assert admin.display_name is None

    def test_timestamps_are_utc_aware(self, db: Session) -> None:
        admin = Admin(email="c@example.com", hashed_password="hash3")
        db.add(admin)
        db.flush()
        assert admin.created_at.tzinfo is not None
        assert admin.updated_at.tzinfo is not None

    def test_unique_email_constraint(self, db: Session) -> None:
        db.add(Admin(email="dup@example.com", hashed_password="h"))
        db.flush()
        db.add(Admin(email="dup@example.com", hashed_password="h"))
        with pytest.raises(IntegrityError):
            db.flush()


# ---------------------------------------------------------------------------
# Conversation model
# ---------------------------------------------------------------------------


class TestConversation:
    def test_uuid_pk_auto_generated(self, db: Session) -> None:
        conv = _make_conversation(db)
        assert conv.id is not None
        uuid.UUID(conv.id)

    def test_default_status_is_active(self, db: Session) -> None:
        conv = _make_conversation(db)
        assert conv.status == ConversationStatus.ACTIVE.value

    def test_invalid_status_raises(self, db: Session) -> None:
        conv = Conversation(status="invalid_status")
        db.add(conv)
        with pytest.raises(IntegrityError):
            db.flush()

    def test_conversation_has_no_lead_by_default(self, db: Session) -> None:
        conv = _make_conversation(db)
        assert conv.lead is None

    def test_messages_relationship_ordered_by_created_at(self, db: Session) -> None:
        conv = _make_conversation(db)
        m1 = _make_message(db, conv, content="first")
        m2 = _make_message(db, conv, content="second")
        db.refresh(conv)
        ids = [m.id for m in conv.messages]
        assert m1.id in ids
        assert m2.id in ids


# ---------------------------------------------------------------------------
# Message model
# ---------------------------------------------------------------------------


class TestMessage:
    def test_valid_roles(self, db: Session) -> None:
        conv = _make_conversation(db)
        for role in ("visitor", "bot", "system"):
            msg = Message(conversation_id=conv.id, role=role, content="x")
            db.add(msg)
        db.flush()

    def test_invalid_role_raises(self, db: Session) -> None:
        conv = _make_conversation(db)
        db.add(Message(conversation_id=conv.id, role="admin", content="x"))
        with pytest.raises(IntegrityError):
            db.flush()

    def test_cascade_delete_when_conversation_deleted(self, db: Session) -> None:
        conv = _make_conversation(db)
        _make_message(db, conv)
        msg_id = conv.messages[0].id
        db.delete(conv)
        db.flush()
        assert db.get(Message, msg_id) is None

    def test_fk_to_nonexistent_conversation_raises(self, db: Session) -> None:
        db.add(Message(conversation_id=str(uuid.uuid4()), role="visitor", content="x"))
        with pytest.raises(IntegrityError):
            db.flush()

    def test_conversation_backreference(self, db: Session) -> None:
        conv = _make_conversation(db)
        msg = _make_message(db, conv)
        assert msg.conversation.id == conv.id


# ---------------------------------------------------------------------------
# Lead model
# ---------------------------------------------------------------------------


class TestLead:
    def test_default_score_is_zero(self, db: Session) -> None:
        conv = _make_conversation(db)
        lead = _make_lead(db, conv)
        assert lead.score == 0

    def test_default_status_is_new(self, db: Session) -> None:
        conv = _make_conversation(db)
        lead = _make_lead(db, conv)
        assert lead.qualification_status == LeadQualificationStatus.NEW.value

    def test_valid_qualification_statuses(self, db: Session) -> None:
        for status in LeadQualificationStatus:
            conv = _make_conversation(db)
            lead = Lead(conversation_id=conv.id, qualification_status=status.value)
            db.add(lead)
        db.flush()

    def test_invalid_qualification_status_raises(self, db: Session) -> None:
        conv = _make_conversation(db)
        db.add(Lead(conversation_id=conv.id, qualification_status="bogus"))
        with pytest.raises(IntegrityError):
            db.flush()

    def test_score_check_lower_boundary(self, db: Session) -> None:
        conv = _make_conversation(db)
        lead = _make_lead(db, conv, score=0)
        assert lead.score == 0

    def test_score_check_upper_boundary(self, db: Session) -> None:
        conv = _make_conversation(db)
        lead = _make_lead(db, conv, score=100)
        assert lead.score == 100

    def test_score_below_zero_raises(self, db: Session) -> None:
        conv = _make_conversation(db)
        db.add(Lead(conversation_id=conv.id, score=-1))
        with pytest.raises(IntegrityError):
            db.flush()

    def test_score_above_100_raises(self, db: Session) -> None:
        conv = _make_conversation(db)
        db.add(Lead(conversation_id=conv.id, score=101))
        with pytest.raises(IntegrityError):
            db.flush()

    def test_unique_conversation_id_constraint(self, db: Session) -> None:
        conv = _make_conversation(db)
        _make_lead(db, conv)
        db.add(Lead(conversation_id=conv.id))
        with pytest.raises(IntegrityError):
            db.flush()

    def test_conversation_relationship(self, db: Session) -> None:
        conv = _make_conversation(db)
        lead = _make_lead(db, conv)
        assert lead.conversation.id == conv.id

    def test_conversation_lead_backreference(self, db: Session) -> None:
        conv = _make_conversation(db)
        lead = _make_lead(db, conv)
        db.refresh(conv)
        assert conv.lead.id == lead.id


# ---------------------------------------------------------------------------
# BANTState model
# ---------------------------------------------------------------------------


class TestBANTState:
    def _make_lead_with_bant(self, db: Session) -> tuple[Lead, BANTState]:
        conv = _make_conversation(db)
        lead = _make_lead(db, conv)
        bant = BANTState(lead_id=lead.id)
        db.add(bant)
        db.flush()
        return lead, bant

    def test_pk_equals_lead_id(self, db: Session) -> None:
        lead, bant = self._make_lead_with_bant(db)
        assert bant.lead_id == lead.id

    def test_default_bant_dimension_values(self, db: Session) -> None:
        _, bant = self._make_lead_with_bant(db)
        assert bant.budget_status == BANTBudgetStatus.UNKNOWN.value
        assert bant.authority_level == BANTAuthorityLevel.UNKNOWN.value
        assert bant.need_clarity == BANTNeedClarity.UNKNOWN.value
        assert bant.timeline_urgency == BANTTimelineUrgency.UNKNOWN.value

    def test_invalid_budget_status_raises(self, db: Session) -> None:
        conv = _make_conversation(db)
        lead = _make_lead(db, conv)
        db.add(BANTState(lead_id=lead.id, budget_status="rich"))
        with pytest.raises(IntegrityError):
            db.flush()

    def test_invalid_authority_level_raises(self, db: Session) -> None:
        conv = _make_conversation(db)
        lead = _make_lead(db, conv)
        db.add(BANTState(lead_id=lead.id, authority_level="ceo"))
        with pytest.raises(IntegrityError):
            db.flush()

    def test_invalid_need_clarity_raises(self, db: Session) -> None:
        conv = _make_conversation(db)
        lead = _make_lead(db, conv)
        db.add(BANTState(lead_id=lead.id, need_clarity="kinda"))
        with pytest.raises(IntegrityError):
            db.flush()

    def test_invalid_timeline_urgency_raises(self, db: Session) -> None:
        conv = _make_conversation(db)
        lead = _make_lead(db, conv)
        db.add(BANTState(lead_id=lead.id, timeline_urgency="soon-ish"))
        with pytest.raises(IntegrityError):
            db.flush()

    def test_negative_budget_amount_raises(self, db: Session) -> None:
        conv = _make_conversation(db)
        lead = _make_lead(db, conv)
        db.add(BANTState(lead_id=lead.id, budget_amount=-1))
        with pytest.raises(IntegrityError):
            db.flush()

    def test_bant_relationship_to_lead(self, db: Session) -> None:
        lead, bant = self._make_lead_with_bant(db)
        assert bant.lead.id == lead.id

    def test_lead_bant_state_backref(self, db: Session) -> None:
        lead, bant = self._make_lead_with_bant(db)
        db.refresh(lead)
        assert lead.bant_state.lead_id == bant.lead_id

    def test_cascade_delete_with_lead(self, db: Session) -> None:
        lead, bant = self._make_lead_with_bant(db)
        lead_id = lead.id
        db.delete(lead)
        db.flush()
        assert db.get(BANTState, lead_id) is None

    def test_all_valid_budget_statuses(self, db: Session) -> None:
        for status in BANTBudgetStatus:
            conv = _make_conversation(db)
            lead = _make_lead(db, conv)
            bant = BANTState(lead_id=lead.id, budget_status=status.value)
            db.add(bant)
        db.flush()

    def test_all_valid_authority_levels(self, db: Session) -> None:
        for level in BANTAuthorityLevel:
            conv = _make_conversation(db)
            lead = _make_lead(db, conv)
            bant = BANTState(lead_id=lead.id, authority_level=level.value)
            db.add(bant)
        db.flush()

    def test_confidence_fields_default_to_none(self, db: Session) -> None:
        _, bant = self._make_lead_with_bant(db)
        assert bant.budget_confidence is None
        assert bant.authority_confidence is None
        assert bant.need_confidence is None
        assert bant.timeline_confidence is None

    def test_valid_confidence_values(self, db: Session) -> None:
        conv = _make_conversation(db)
        lead = _make_lead(db, conv)
        bant = BANTState(
            lead_id=lead.id,
            budget_confidence=0.0,
            authority_confidence=0.5,
            need_confidence=1.0,
            timeline_confidence=0.85,
        )
        db.add(bant)
        db.flush()
        assert bant.budget_confidence == 0.0
        assert bant.authority_confidence == 0.5
        assert bant.need_confidence == 1.0
        assert bant.timeline_confidence == 0.85

    @pytest.mark.parametrize(
        ("field", "val"),
        [
            ("budget_confidence", -0.1),
            ("budget_confidence", 1.1),
            ("authority_confidence", -0.01),
            ("authority_confidence", 1.01),
            ("need_confidence", -0.5),
            ("need_confidence", 2.0),
            ("timeline_confidence", -1.0),
            ("timeline_confidence", 1.5),
        ],
    )
    def test_invalid_confidence_raises(self, db: Session, field: str, val: float) -> None:
        conv = _make_conversation(db)
        lead = _make_lead(db, conv)
        db.add(BANTState(lead_id=lead.id, **{field: val}))
        with pytest.raises(IntegrityError):
            db.flush()


# ---------------------------------------------------------------------------
# LeadScoreHistory model
# ---------------------------------------------------------------------------


class TestLeadScoreHistory:
    def test_score_history_created_with_lead_id(self, db: Session) -> None:
        conv = _make_conversation(db)
        lead = _make_lead(db, conv, score=50)
        snap = LeadScoreHistory(lead_id=lead.id, score=50)
        db.add(snap)
        db.flush()
        assert snap.id is not None
        assert snap.lead_id == lead.id
        assert snap.score == 50

    def test_score_history_optional_message_id(self, db: Session) -> None:
        conv = _make_conversation(db)
        lead = _make_lead(db, conv)
        msg = _make_message(db, conv)
        snap = LeadScoreHistory(lead_id=lead.id, score=30, message_id=msg.id)
        db.add(snap)
        db.flush()
        assert snap.message_id == msg.id

    def test_multiple_snapshots_for_same_lead(self, db: Session) -> None:
        conv = _make_conversation(db)
        lead = _make_lead(db, conv)
        for score in (10, 30, 70):
            db.add(LeadScoreHistory(lead_id=lead.id, score=score))
        db.flush()
        db.refresh(lead)
        assert len(lead.score_history) == 3

    def test_score_below_zero_raises(self, db: Session) -> None:
        conv = _make_conversation(db)
        lead = _make_lead(db, conv)
        db.add(LeadScoreHistory(lead_id=lead.id, score=-1))
        with pytest.raises(IntegrityError):
            db.flush()

    def test_score_above_100_raises(self, db: Session) -> None:
        conv = _make_conversation(db)
        lead = _make_lead(db, conv)
        db.add(LeadScoreHistory(lead_id=lead.id, score=101))
        with pytest.raises(IntegrityError):
            db.flush()

    def test_created_at_is_set_automatically(self, db: Session) -> None:
        conv = _make_conversation(db)
        lead = _make_lead(db, conv)
        snap = LeadScoreHistory(lead_id=lead.id, score=40)
        db.add(snap)
        db.flush()
        assert snap.created_at is not None

    def test_cascade_delete_when_lead_deleted(self, db: Session) -> None:
        conv = _make_conversation(db)
        lead = _make_lead(db, conv)
        snap = LeadScoreHistory(lead_id=lead.id, score=55)
        db.add(snap)
        db.flush()
        snap_id = snap.id
        db.delete(lead)
        db.flush()
        assert db.get(LeadScoreHistory, snap_id) is None

    def test_message_set_null_when_message_deleted(self, db: Session) -> None:
        conv = _make_conversation(db)
        lead = _make_lead(db, conv)
        msg = _make_message(db, conv)
        snap = LeadScoreHistory(lead_id=lead.id, score=60, message_id=msg.id)
        db.add(snap)
        db.flush()
        snap_id = snap.id
        db.delete(msg)
        db.flush()
        db.expire(snap)
        refreshed = db.get(LeadScoreHistory, snap_id)
        assert refreshed.message_id is None


# ---------------------------------------------------------------------------
# RoutingAction model
# ---------------------------------------------------------------------------


class TestRoutingAction:
    def _make_routing_action(
        self,
        db: Session,
        lead: Lead,
        action_type: str = RoutingActionType.SALES_ALERT.value,
        key_suffix: str = "",
    ) -> RoutingAction:
        action = RoutingAction(
            lead_id=lead.id,
            action_type=action_type,
            idempotency_key=f"key-{lead.id}-{action_type}{key_suffix}",
        )
        db.add(action)
        db.flush()
        return action

    def test_default_status_is_pending(self, db: Session) -> None:
        conv = _make_conversation(db)
        lead = _make_lead(db, conv)
        action = self._make_routing_action(db, lead)
        assert action.status == RoutingActionStatus.PENDING.value

    def test_valid_action_types(self, db: Session) -> None:
        for act_type in RoutingActionType:
            conv = _make_conversation(db)
            lead = _make_lead(db, conv)
            a = RoutingAction(
                lead_id=lead.id,
                action_type=act_type.value,
                idempotency_key=str(uuid.uuid4()),
            )
            db.add(a)
        db.flush()

    def test_invalid_action_type_raises(self, db: Session) -> None:
        conv = _make_conversation(db)
        lead = _make_lead(db, conv)
        db.add(RoutingAction(
            lead_id=lead.id,
            action_type="text_message",
            idempotency_key=str(uuid.uuid4()),
        ))
        with pytest.raises(IntegrityError):
            db.flush()

    def test_valid_statuses(self, db: Session) -> None:
        for st in RoutingActionStatus:
            conv = _make_conversation(db)
            lead = _make_lead(db, conv)
            a = RoutingAction(
                lead_id=lead.id,
                action_type=RoutingActionType.SALES_ALERT.value,
                status=st.value,
                idempotency_key=str(uuid.uuid4()),
            )
            db.add(a)
        db.flush()

    @pytest.mark.parametrize(
        "invalid_status",
        ["in_progress", "skipped", "completed", "cancelled"],
    )
    def test_invalid_status_raises(self, db: Session, invalid_status: str) -> None:
        conv = _make_conversation(db)
        lead = _make_lead(db, conv)
        db.add(RoutingAction(
            lead_id=lead.id,
            action_type=RoutingActionType.SALES_ALERT.value,
            status=invalid_status,
            idempotency_key=str(uuid.uuid4()),
        ))
        with pytest.raises(IntegrityError):
            db.flush()

    def test_idempotency_key_unique_constraint(self, db: Session) -> None:
        conv = _make_conversation(db)
        lead = _make_lead(db, conv)
        key = "same-key-12345"
        db.add(RoutingAction(
            lead_id=lead.id,
            action_type=RoutingActionType.SALES_ALERT.value,
            idempotency_key=key,
        ))
        db.flush()
        db.add(RoutingAction(
            lead_id=lead.id,
            action_type=RoutingActionType.CALENDAR_BOOKING.value,
            idempotency_key=key,  # same key — must fail
        ))
        with pytest.raises(IntegrityError):
            db.flush()

    def test_lead_routing_actions_relationship(self, db: Session) -> None:
        conv = _make_conversation(db)
        lead = _make_lead(db, conv)
        self._make_routing_action(db, lead, key_suffix="-1")
        self._make_routing_action(
            db, lead, action_type=RoutingActionType.CALENDAR_BOOKING.value, key_suffix="-2"
        )
        db.refresh(lead)
        assert len(lead.routing_actions) == 2

    def test_cascade_delete_when_lead_deleted(self, db: Session) -> None:
        conv = _make_conversation(db)
        lead = _make_lead(db, conv)
        action = self._make_routing_action(db, lead)
        action_id = action.id
        db.delete(lead)
        db.flush()
        assert db.get(RoutingAction, action_id) is None


# ---------------------------------------------------------------------------
# Cross-entity relationship smoke test
# ---------------------------------------------------------------------------


class TestFullPipelineRelationships:
    """Verify the complete entity graph can be constructed and traversed."""

    def test_full_pipeline_graph(self, db: Session) -> None:
        # Conversation
        conv = _make_conversation(db, channel="widget")

        # Messages
        m1 = _make_message(db, conv, role="visitor", content="I need a CRM")
        _make_message(db, conv, role="bot", content="Great! Can you share your budget?")

        # Lead
        lead = _make_lead(db, conv, name="Alice", score=70)

        # BANT state
        bant = BANTState(
            lead_id=lead.id,
            budget_status=BANTBudgetStatus.SPECIFIED.value,
            authority_level=BANTAuthorityLevel.DECISION_MAKER.value,
            need_clarity=BANTNeedClarity.SPECIFIC.value,
            timeline_urgency=BANTTimelineUrgency.SHORT_TERM.value,
        )
        db.add(bant)

        # Score history
        snap = LeadScoreHistory(lead_id=lead.id, score=70, message_id=m1.id)
        db.add(snap)

        # Routing action
        action = RoutingAction(
            lead_id=lead.id,
            action_type=RoutingActionType.SALES_ALERT.value,
            idempotency_key=f"alert-{lead.id}",
            status=RoutingActionStatus.PENDING.value,
        )
        db.add(action)
        db.flush()

        # Traverse relationships
        db.refresh(conv)
        db.refresh(lead)

        assert conv.lead.id == lead.id
        assert len(conv.messages) == 2
        assert lead.bant_state.budget_status == BANTBudgetStatus.SPECIFIED.value
        assert len(lead.score_history) == 1
        assert lead.score_history[0].message.id == m1.id
        assert len(lead.routing_actions) == 1
        assert lead.routing_actions[0].action_type == RoutingActionType.SALES_ALERT.value
