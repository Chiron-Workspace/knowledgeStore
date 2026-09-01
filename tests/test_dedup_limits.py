"""Giới hạn ĐÃ BIẾT của dò trùng trigram — khoá bằng test, KHÔNG chỉnh ngưỡng.

Chỉnh mù là đoán; hạ ngưỡng chắc chắn kéo theo false negative ở nơi khác.
Quyết định nâng cấp (pgvector/embedding) chờ dữ liệu thật từ Mnemosyne.

Các con số dưới đây đo trên chính cluster này (PostgreSQL 18.6, pg_trgm 1.6,
collation en_US.UTF-8, provider libc). Xem NOTES.md — chúng KHÁC với bảng
evidence của lần build trước.
"""

from __future__ import annotations

import pytest

from ks import settings
from ks.ingest import ingest_concepts
from ks.models import ConceptDraft, SourceModule


def _sim(conn, a: str, b: str) -> float:
    with conn.cursor() as cur:
        cur.execute("SELECT similarity(%s, %s)", (a, b))
        return float(cur.fetchone()[0])


def _draft(title: str) -> ConceptDraft:
    return ConceptDraft(title, "Vật lý", "x", SourceModule.MNEMOSYNE)


def test_numbered_variants_are_wrongly_deduped(conn):
    """LỖI ĐÃ BIẾT: hai định luật khác nhau bị gộp làm một chỉ vì tên khác mỗi chữ số."""
    ingest_concepts(conn, [_draft("Định luật Newton 1")])
    result = ingest_concepts(conn, [_draft("Định luật Newton 2")])
    item = result.ingested[0]
    assert item.created is False, "Nếu test này đỏ: hành vi dedup đã đổi, đọc NOTES.md trước khi sửa"


@pytest.mark.parametrize(
    "a, b, expected",
    [
        ("Định luật Newton 1", "Định luật Newton 2", 0.8095),
        ("khúc xạ", "phản xạ", 0.2308),
        ("Định luật Ohm", "Định luật Newton 2", 0.4348),
    ],
)
def test_evidence_point_similarity_do_duoc(conn, a, b, expected):
    """Số đo thật, không phải số nhớ lại. Đổi Postgres/collation → số này đổi."""
    assert _sim(conn, a, b) == pytest.approx(expected, abs=0.001)


def test_cap_khuc_xa_phan_xa_KHONG_bi_gop_tren_cluster_nay(conn):
    """Trên cluster này similarity chỉ 0.23 — dưới ngưỡng 0.6, nên KHÔNG gộp.
    Lần build trước ghi 0.677 (gộp nhầm). Khác biệt chưa giải thích được."""
    ingest_concepts(conn, [_draft("khúc xạ")])
    result = ingest_concepts(conn, [_draft("phản xạ")])
    assert result.ingested[0].created is True


def test_nguong_gop_van_la_0_6(conn):
    """Khoá hằng số: đổi ngưỡng là quyết định của Agent A, không phải của code."""
    assert settings.DUPLICATE_THRESHOLD == 0.6
