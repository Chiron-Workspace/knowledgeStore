"""Ghi khái niệm vào KS + dò trùng bằng full-text trigram.

FAIL-LOUD: lỗi DB văng thẳng ra dạng psycopg.Error. Đối lập có chủ đích với
save_transcript (không bao giờ raise). Wrapper HTTP tự bắt → 503.
"""

from __future__ import annotations

from uuid import UUID

import psycopg

from ks import settings
from ks.models import (
    ConceptDraft,
    DuplicateCandidate,
    IngestedConcept,
    IngestResult,
)

# similarity() thay vì toán tử `%` để ngưỡng không phụ thuộc GUC
# pg_trgm.similarity_threshold của session. Đổi lại là không dùng GIN index —
# chấp nhận được ở quy mô một người dùng, ghi làm nợ kỹ thuật.
_CANDIDATE_SQL = """
SELECT id, title, similarity(title, %(title)s) AS score
FROM ks.nodes
WHERE merged_into_id IS NULL
  AND similarity(title, %(title)s) >= %(floor)s
ORDER BY score DESC, title ASC
LIMIT %(limit)s
"""

_INSERT_SQL = """
INSERT INTO ks.nodes (title, subject, summary, source_module)
VALUES (%s, %s, %s, %s)
RETURNING id
"""


def find_candidates(
    conn: psycopg.Connection,
    title: str,
    *,
    floor: float = settings.CANDIDATE_FLOOR,
    limit: int = settings.CANDIDATE_LIMIT,
) -> tuple[DuplicateCandidate, ...]:
    """Node có sẵn giống `title`, sắp giảm dần theo similarity.

    Bỏ qua node đã merge (merged_into_id khác NULL) — không gợi ý gộp vào một
    node đã chết.
    """
    with conn.cursor() as cur:
        cur.execute(_CANDIDATE_SQL, {"title": title, "floor": floor, "limit": limit})
        rows = cur.fetchall()
    return tuple(
        DuplicateCandidate(node_id=row[0], title=row[1], score=float(row[2]))
        for row in rows
    )


def _pick_duplicate(
    candidates: tuple[DuplicateCandidate, ...],
    threshold: float,
) -> DuplicateCandidate | None:
    """Candidate đầu tiên đạt ngưỡng gộp, hoặc None."""
    for cand in candidates:
        if cand.score >= threshold:
            return cand
    return None


def ingest_concepts(
    conn: psycopg.Connection,
    drafts: list[ConceptDraft] | tuple[ConceptDraft, ...],
    *,
    threshold: float = settings.DUPLICATE_THRESHOLD,
) -> IngestResult:
    """Ghi từng draft: khớp node có sẵn nếu similarity >= ngưỡng, không thì tạo mới.

    Không commit — transaction thuộc về caller. Draft trong cùng lô nhìn thấy
    nhau: draft thứ hai trùng draft thứ nhất sẽ khớp vào node vừa tạo.
    """
    ingested: list[IngestedConcept] = []
    for draft in drafts:
        candidates = find_candidates(conn, draft.title)
        match = _pick_duplicate(candidates, threshold)
        if match is not None:
            node_id: UUID = match.node_id
            created = False
        else:
            with conn.cursor() as cur:
                cur.execute(
                    _INSERT_SQL,
                    (
                        draft.title,
                        draft.subject,
                        draft.summary,
                        draft.source_module.value,
                    ),
                )
                node_id = cur.fetchone()[0]
            created = True

        ingested.append(
            IngestedConcept(
                draft=draft,
                node_id=node_id,
                created=created,
                candidates=candidates,
            )
        )

    return IngestResult(ingested=tuple(ingested))
