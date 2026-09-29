from types import SimpleNamespace
from app.services.scoring import score_bant
def bant(b="specified",a="decision_maker",n="specific",t="immediate"):
    return SimpleNamespace(budget_status=b,authority_level=a,need_clarity=n,timeline_urgency=t,budget_confidence=.9,authority_confidence=.9,need_confidence=.9,timeline_confidence=.9)
def test_full_bant_scores_100():
    r=score_bant(bant()); assert r.score==100 and r.completeness==100 and r.status.value=="high_intent"
def test_long_term_prevents_high_intent():
    r=score_bant(bant(t="long_term")); assert r.score==81 and r.status.value=="qualified"
def test_empty_bant_is_new():
    r=score_bant(bant("unknown","unknown","unknown","unknown")); assert r.score==0 and r.completeness==0 and r.status.value=="new"
