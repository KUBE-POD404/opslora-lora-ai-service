from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.ai import AIKnowledgeChunk, AIKnowledgeSource
from app.schemas import Citation, KnowledgeIngestRequest

_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,}")
_MAX_CHUNK_CHARS = 1200
_CHUNK_OVERLAP_CHARS = 150
_STOP_WORDS = {
    "about",
    "after",
    "from",
    "have",
    "into",
    "that",
    "the",
    "this",
    "what",
    "when",
    "where",
    "which",
    "with",
    "your",
}


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: AIKnowledgeChunk
    source: AIKnowledgeSource
    score: int


def _terms(text: str) -> list[str]:
    return [word.lower() for word in _WORD_RE.findall(text) if word.lower() not in _STOP_WORDS]


def _split_long_paragraph(paragraph: str, *, max_chars: int) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(paragraph):
        end = min(start + max_chars, len(paragraph))
        chunks.append(paragraph[start:end].strip())
        if end == len(paragraph):
            break
        start = max(0, end - _CHUNK_OVERLAP_CHARS)
    return chunks


def _append_paragraph(chunks: list[str], current: str, paragraph: str, *, max_chars: int) -> str:
    candidate = f"{current}\n\n{paragraph}" if current else paragraph
    if len(candidate) > max_chars and current:
        chunks.append(current.strip())
        return paragraph
    return candidate


def chunk_text(content: str, *, max_chars: int = _MAX_CHUNK_CHARS) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(_split_long_paragraph(paragraph, max_chars=max_chars))
            continue
        current = _append_paragraph(chunks, current, paragraph, max_chars=max_chars)
    if current:
        chunks.append(current.strip())
    return chunks or [content.strip()]


def ingest_knowledge(db: Session, request: KnowledgeIngestRequest) -> tuple[AIKnowledgeSource, int]:
    source = AIKnowledgeSource(
        organization_id=request.organization_id,
        created_by_user_id=request.user_id,
        source_type=request.source_type,
        source_uri=request.source_uri,
        visibility_scope=request.visibility_scope,
        retention_policy=request.retention_policy,
        status="indexed",
    )
    db.add(source)
    db.flush()

    chunks = chunk_text(request.content)
    for index, chunk in enumerate(chunks):
        db.add(
            AIKnowledgeChunk(
                organization_id=request.organization_id,
                created_by_user_id=request.user_id,
                source_id=source.id,
                chunk_index=index,
                content=chunk,
                vector_id=None,
                metadata_json={"retrieval": "keyword"},
            )
        )
    db.commit()
    db.refresh(source)
    return source, len(chunks)


def retrieve_context(db: Session, *, organization_id: str, query: str, limit: int = 5) -> list[RetrievedChunk]:
    terms = Counter(_terms(query))
    if not terms:
        return []

    filters = [AIKnowledgeChunk.content.ilike(f"%{term}%") for term in terms]
    rows = db.execute(
        select(AIKnowledgeChunk, AIKnowledgeSource)
        .join(AIKnowledgeSource, AIKnowledgeChunk.source_id == AIKnowledgeSource.id)
        .where(AIKnowledgeChunk.organization_id == organization_id)
        .where(or_(*filters))
        .limit(50)
    ).all()

    ranked = [_rank_chunk(chunk, source, terms) for chunk, source in rows]
    ranked = [item for item in ranked if item.score > 0]
    ranked.sort(key=lambda item: (-item.score, item.chunk.chunk_index))
    return ranked[:limit]


def _rank_chunk(
    chunk: AIKnowledgeChunk, source: AIKnowledgeSource, terms: Counter[str]
) -> RetrievedChunk:
    text = chunk.content.lower()
    chunk_terms = Counter(_terms(chunk.content))
    exact_score = sum(chunk_terms.get(term, 0) * weight * 3 for term, weight in terms.items())
    substring_score = sum(text.count(term) * weight for term, weight in terms.items())
    coverage_score = sum(1 for term in terms if chunk_terms.get(term, 0)) * 5
    phrase = " ".join(terms)
    phrase_score = 10 if len(terms) > 1 and phrase in text else 0
    score = exact_score + substring_score + coverage_score + phrase_score
    return RetrievedChunk(chunk=chunk, source=source, score=score)


def format_context(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "No tenant knowledge context was retrieved."
    blocks = []
    for idx, item in enumerate(chunks, start=1):
        blocks.append(
            f"[source {idx}] source_id={item.source.id} chunk_id={item.chunk.id}\n"
            f"{item.chunk.content}"
        )
    return "\n\n".join(blocks)


def citations_for(chunks: list[RetrievedChunk]) -> list[Citation]:
    citations: list[Citation] = []
    for item in chunks:
        snippet = item.chunk.content.replace("\n", " ")[:240]
        citations.append(
            Citation(
                source_id=item.source.id,
                chunk_id=item.chunk.id,
                chunk_index=item.chunk.chunk_index,
                source_uri=item.source.source_uri,
                snippet=snippet,
            )
        )
    return citations
