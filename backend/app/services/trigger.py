from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher


@dataclass(frozen=True)
class TriggerContext:
    text: str
    status: str
    automatic_enabled: bool
    new_characters: int
    minimum_characters: int = 300
    codex_running: bool = False
    last_codex_at: datetime | None = None
    codex_cooldown_seconds: int = 60
    last_suggestion_at: datetime | None = None
    suggestion_cooldown_seconds: int = 180
    confidence: float = 1.0


@dataclass(frozen=True)
class TriggerDecision:
    invoke: bool
    trigger: str | None
    suppressed_by: str | None


def decide_trigger(context: TriggerContext, manual: bool = False, meeting_end: bool = False) -> TriggerDecision:
    now = datetime.now(timezone.utc)
    if manual:
        return TriggerDecision(True, "manual_ask", None)
    if meeting_end:
        return TriggerDecision(True, "meeting_end", None)
    suppressors = [
        (context.status != "active", "meeting_not_active"),
        (not context.automatic_enabled, "automatic_disabled"),
        (context.codex_running, "codex_running"),
        (context.new_characters < context.minimum_characters, "insufficient_transcript"),
        (context.confidence < 0.45, "low_confidence"),
        (bool(context.last_codex_at and now - context.last_codex_at < timedelta(seconds=context.codex_cooldown_seconds)), "codex_cooldown"),
        (bool(context.last_suggestion_at and now - context.last_suggestion_at < timedelta(seconds=context.suggestion_cooldown_seconds)), "suggestion_cooldown"),
    ]
    for active, reason in suppressors:
        if active:
            return TriggerDecision(False, None, reason)
    lowered = context.text.lower()
    if "codex" in lowered or "助理" in lowered:
        return TriggerDecision(True, "direct_mention", None)
    if "?" in context.text or "？" in context.text:
        return TriggerDecision(True, "explicit_question", None)
    if any(word in context.text for word in ("決定", "結論", "同意", "風險", "問題")):
        return TriggerDecision(True, "decision_keyword", None)
    return TriggerDecision(True, "periodic_analysis", None)


def similar(a: str, b: str, threshold: float = 0.82) -> bool:
    normalize = lambda value: "".join(value.lower().split())
    left, right = normalize(a), normalize(b)
    return bool(left and right and (left == right or SequenceMatcher(None, left, right).ratio() >= threshold))


def merge_overlap(previous: str, current: str) -> str:
    """Remove repeated prefix caused by overlapping STT windows."""
    max_overlap = min(len(previous), len(current))
    for length in range(max_overlap, 3, -1):
        if previous[-length:].lower() == current[:length].lower():
            return current[length:].lstrip()
    return current
