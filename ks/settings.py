"""Hằng số và cấu hình đọc từ môi trường. Không giá trị bí mật hard-code."""

from __future__ import annotations

import os

# ---------------------------------------------------------------- database

DATABASE_URL_ENV = "KS_DATABASE_URL"
TEST_DATABASE_URL_ENV = "KS_TEST_DATABASE_URL"


def database_url() -> str:
    """URL Postgres. Thiếu biến → raise, không đoán mặc định."""
    url = os.environ.get(DATABASE_URL_ENV, "")
    if not url:
        raise RuntimeError(f"Thiếu biến môi trường {DATABASE_URL_ENV}")
    return url


# ---------------------------------------------------------------- dò trùng

# Ngưỡng gộp: similarity >= ngưỡng → coi là cùng khái niệm.
# 0.6 là quyết định đã chốt. Xem NOTES.md §giới hạn trước khi chỉnh.
DUPLICATE_THRESHOLD = 0.6

# Sàn ghi nhận candidate: dưới ngưỡng gộp nhưng vẫn đáng log (đo false negative).
CANDIDATE_FLOOR = 0.3

# Số candidate tối đa trả về mỗi draft.
CANDIDATE_LIMIT = 5

# ---------------------------------------------------------------- edges

# Số node lân cận đưa vào prompt gợi ý edge.
EDGE_SUGGESTION_TOP_K = 8

# Ngân sách token cho output LLM.
#
# ĐO ĐƯỢC THẬT: deepseek-v4-flash là model REASONING — reasoning token TÍNH VÀO
# max_tokens. Một lần gọi gợi ý edge với 2 ứng viên tốn 222 completion token,
# trong đó 158 là reasoning (71%). Lượng reasoning thay đổi mỗi lần chạy, nên
# max_tokens=1000 từng để lại ~15 token cho JSON và cắt ngang giữa chừng.
#
# Đặt rộng tay: chi phí chỉ phát sinh theo token THỰC SỰ sinh ra, còn cắt ngang
# thì hỏng cả lô. Đừng hạ hai số này xuống theo độ dài output nhìn thấy được.
EDGE_SUGGESTION_MAX_TOKENS = 4000
EXTRACTION_MAX_TOKENS = 4000

# ---------------------------------------------------------------- http

HTTP_TOKEN_ENV = "KS_HTTP_TOKEN"
HTTP_PORT_ENV = "KS_HTTP_PORT"
DEFAULT_HTTP_PORT = 8080

# Trần limit của GET /nodes. Vượt trần → 400, KHÔNG âm thầm cắt.
MAX_NODE_LIMIT = 500
DEFAULT_NODE_LIMIT = 50

# ---------------------------------------------------------------- extraction

# Số lần thử lại tối đa cho một transcript.
MAX_EXTRACTION_ATTEMPTS = 5
