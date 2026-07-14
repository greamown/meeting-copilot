import re

from app.db.base import ProjectGlossary


def _replace_many(text: str, sources: set[str], target: str) -> str:
    candidates = sorted(
        {source for source in sources if source and source.casefold() != target.casefold()},
        key=len,
        reverse=True,
    )
    if not candidates:
        return text
    pattern = "|".join(re.escape(source) for source in candidates)
    return re.sub(pattern, lambda _: target, text, flags=re.IGNORECASE)


def normalize_transcript(text: str, glossary: list[ProjectGlossary]) -> str:
    """Normalize recognized aliases while preserving the transcript's language."""
    normalized = text
    for row in glossary:
        preferred = row.preferred_spelling.strip() or row.term
        aliases = sorted(
            {str(value).strip() for value in [*list(row.aliases_json or []), row.term] if value},
            key=len,
            reverse=True,
        )
        normalized = _replace_many(normalized, set(aliases), preferred)
    return normalized


def normalize_translation(text: str, glossary: list[ProjectGlossary]) -> str:
    """Apply deterministic translated spelling and do-not-translate rules."""
    normalized = text
    for row in glossary:
        preferred = row.preferred_spelling.strip() or row.term
        if row.do_not_translate:
            candidates = [row.translation, *list(row.aliases_json or [])]
            target = preferred
        elif row.translation.strip():
            candidates = [row.term, row.preferred_spelling, *list(row.aliases_json or [])]
            target = row.translation.strip()
        else:
            continue
        terms = {str(value).strip() for value in candidates if value}
        normalized = _replace_many(normalized, terms, target)
    return normalized
