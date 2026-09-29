"""Deterministic BANT scoring and qualification rules."""
from __future__ import annotations
from dataclasses import dataclass
from app.domain.enums import (
    BANTAuthorityLevel, BANTBudgetStatus, BANTNeedClarity,
    BANTTimelineUrgency, LeadQualificationStatus,
)

@dataclass(frozen=True)
class ScoreResult:
    score: int
    completeness: int
    status: LeadQualificationStatus
    band: str

def score_bant(bant) -> ScoreResult:
    budget = {
        BANTBudgetStatus.UNKNOWN.value: 0,
        BANTBudgetStatus.VAGUE.value: 10,
        BANTBudgetStatus.SPECIFIED.value: 25,
        BANTBudgetStatus.NONE_AVAILABLE.value: 0,
    }.get(bant.budget_status, 0)
    authority = {
        BANTAuthorityLevel.UNKNOWN.value: 0,
        BANTAuthorityLevel.INFLUENCER.value: 8,
        BANTAuthorityLevel.EVALUATOR.value: 14,
        BANTAuthorityLevel.DECISION_MAKER.value: 20,
    }.get(bant.authority_level, 0)
    need = {
        BANTNeedClarity.UNKNOWN.value: 0,
        BANTNeedClarity.VAGUE.value: 10,
        BANTNeedClarity.CLEAR.value: 20,
        BANTNeedClarity.SPECIFIC.value: 30,
    }.get(bant.need_clarity, 0)
    timeline = {
        BANTTimelineUrgency.UNKNOWN.value: 0,
        BANTTimelineUrgency.LONG_TERM.value: 6,
        BANTTimelineUrgency.SHORT_TERM.value: 20,
        BANTTimelineUrgency.IMMEDIATE.value: 25,
    }.get(bant.timeline_urgency, 0)
    score = max(0, min(100, budget + authority + need + timeline))
    known = sum([
        bant.budget_status != BANTBudgetStatus.UNKNOWN.value,
        bant.authority_level != BANTAuthorityLevel.UNKNOWN.value,
        bant.need_clarity != BANTNeedClarity.UNKNOWN.value,
        bant.timeline_urgency != BANTTimelineUrgency.UNKNOWN.value,
    ])
    completeness = known * 25
    confidences = [
        bant.budget_confidence, bant.authority_confidence,
        bant.need_confidence, bant.timeline_confidence,
    ]
    credible = [c for c in confidences if c is not None]
    avg_confidence = sum(credible) / len(credible) if credible else 0
    if score >= 70 and completeness >= 75 and avg_confidence >= 0.65 and bant.timeline_urgency != BANTTimelineUrgency.LONG_TERM.value:
        status = LeadQualificationStatus.HIGH_INTENT
    elif score >= 40:
        status = LeadQualificationStatus.QUALIFIED
    elif score > 0:
        status = LeadQualificationStatus.QUALIFYING
    else:
        status = LeadQualificationStatus.NEW
    band = "High" if score >= 70 else "Medium" if score >= 40 else "Low"
    return ScoreResult(score, completeness, status, band)
