"""Kiểu dữ liệu của KS. Tất cả frozen — không mutate sau khi dựng."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import UUID


class SourceModule(str, Enum):
    MNEMOSYNE = "mnemosyne"
    LEXIFLASH = "lexiflash"


class RelationType(str, Enum):
    PREREQUISITE = "prerequisite"
    RELATED = "related"
    CONTRASTS_WITH = "contrasts_with"


class SuggestedBy(str, Enum):
    LLM = "llm"
    MANUAL = "manual"


class EdgeStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


# Quan hệ đối xứng: lưu một chiều, query hai chiều.
SYMMETRIC_RELATIONS = frozenset({RelationType.RELATED, RelationType.CONTRASTS_WITH})


@dataclass(frozen=True)
class ConceptDraft:
    """Một khái niệm chờ ghi. 4 field, tất cả bắt buộc, không optional."""

    title: str
    subject: str
    summary: str
    source_module: SourceModule


@dataclass(frozen=True)
class DuplicateCandidate:
    """Node có sẵn giống draft. score là similarity trigram trên title."""

    node_id: UUID
    title: str
    score: float


@dataclass(frozen=True)
class IngestedConcept:
    """Kết quả ghi một draft.

    candidates populate CẢ KHI created=True — near-miss dưới ngưỡng cũng phải
    log, nếu chỉ log ca merge thì dữ liệu một chiều, không đo được false negative.
    """

    draft: ConceptDraft
    node_id: UUID
    created: bool  # True = tạo mới, False = khớp node có sẵn
    candidates: tuple[DuplicateCandidate, ...]


@dataclass(frozen=True)
class IngestResult:
    ingested: tuple[IngestedConcept, ...]


@dataclass(frozen=True)
class NodeSummary:
    """Cho GET /nodes — KHÔNG có edges."""

    id: UUID
    title: str
    subject: str
    summary: str


@dataclass(frozen=True)
class SaveResult:
    """Kết quả save_transcript. ok=False kèm error thay vì raise."""

    ok: bool
    transcript_id: UUID | None
    error: str | None
