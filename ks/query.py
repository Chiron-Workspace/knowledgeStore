"""Đọc node cho consumer HTTP. Thuần đọc DB, KHÔNG chạm LLM, KHÔNG trả edges."""

from __future__ import annotations

import psycopg

from ks import settings
from ks.models import NodeSummary

# merged_into_id khác NULL → trả node ĐÍCH, đúng MỘT BƯỚC (không walk chain).
# DISTINCT ON gộp nhiều node cùng đích về một dòng. LEFT JOIN + DISTINCT ON làm
# tất cả trong MỘT round-trip.
#
# Bộ lọc áp lên node ĐÃ RESOLVE, không phải node gốc: kết quả trả về luôn khớp
# điều kiện người gọi hỏi, không có chuyện lọc subject='Vật lý' mà nhận về node
# môn Sinh học.
_LIST_SQL = """
SELECT id, title, subject, summary
FROM (
  SELECT DISTINCT ON (COALESCE(t.id, n.id))
         COALESCE(t.id, n.id)                       AS id,
         COALESCE(t.title, n.title)                 AS title,
         COALESCE(t.subject, n.subject)             AS subject,
         COALESCE(t.summary, n.summary)             AS summary,
         COALESCE(t.created_at, n.created_at)       AS created_at
  FROM ks.nodes n
  LEFT JOIN ks.nodes t ON t.id = n.merged_into_id
  -- ::text / ::ks.source_module là bắt buộc: không có cast, Postgres không suy
  -- ra được kiểu của tham số trần trong mệnh đề IS NULL và báo AmbiguousParameter.
  -- (Đừng viết placeholder mẫu vào comment: psycopg vẫn parse comment.)
  WHERE (%(subject)s::text IS NULL OR COALESCE(t.subject, n.subject) = %(subject)s::text)
    AND (%(source_module)s::ks.source_module IS NULL
         OR COALESCE(t.source_module, n.source_module) = %(source_module)s::ks.source_module)
  ORDER BY COALESCE(t.id, n.id), n.created_at
) resolved
ORDER BY title, id
LIMIT %(limit)s
"""


def list_nodes(
    conn: psycopg.Connection,
    *,
    subject: str | None = None,
    source_module: str | None = None,
    limit: int = settings.DEFAULT_NODE_LIMIT,
) -> tuple[NodeSummary, ...]:
    """Danh sách node đã resolve merge. Không có edges — đó là chủ đích."""
    with conn.cursor() as cur:
        cur.execute(
            _LIST_SQL,
            {"subject": subject, "source_module": source_module, "limit": limit},
        )
        rows = cur.fetchall()
    return tuple(
        NodeSummary(id=r[0], title=r[1], subject=r[2], summary=r[3]) for r in rows
    )
