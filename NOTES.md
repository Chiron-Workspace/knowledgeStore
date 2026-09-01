# NOTES — quyết định, giới hạn, và bẫy đã trả giá

## Quyết định đã chốt (không bàn lại)
- Postgres `nodes` + `edges`, **không Neo4j**.
- Node = một khái niệm, **không phải một phiên học**.
- Dò trùng bằng full-text `pg_trgm`, ngưỡng **0.6**. **Không embedding, không pgvector** —
  nâng cấp chờ bằng chứng thật từ Mnemosyne.
- Edge: LLM gợi ý → `pending` → người duyệt → `approved`. **Không auto-approve.**
- `subject` là TEXT tự do, **KHÔNG enum** (Horae không có taxonomy môn học đóng kín).
- `rejected` / `discarded` giữ vĩnh viễn, không xoá — "không hỏi lại câu người dùng đã trả lời".
- Merge node dùng `merged_into_id`, **không xoá cứng**.
- Mnemosyne ghi sau cả phiên, không sau mỗi câu trả lời.
- Lưu transcript raw TRƯỚC, extraction là job riêng retry được.
- LLM client viết riêng cho KS, không import gì từ Horae, nhưng cùng quy ước.

## Hai hàm cốt lõi ĐỐI LẬP nhau có chủ đích
| Hàm | Hành vi |
|---|---|
| `save_transcript` | **KHÔNG BAO GIỜ raise.** Nuốt mọi lỗi kể cả mất kết nối DB → `SaveResult(ok=False)`. Phiên học không được hỏng vì KS chết; Mnemosyne là system of record. |
| `ingest_concepts` | **Fail-loud.** `psycopg.Error` văng thẳng ra. Wrapper HTTP bắt → 503. |

## Giới hạn đã biết — KHÔNG sửa, chỉ khoá bằng test
Dedup trigram gộp nhầm khái niệm tên gần giống. Khoá bằng
`tests/test_dedup_limits.py::test_numbered_variants_are_wrongly_deduped`.

### ⚠️ Số đo THẬT trên cluster hiện tại KHÁC bảng evidence của lần build trước
Đo trên PostgreSQL 18.6, pg_trgm 1.6, collation `en_US.UTF-8`, provider `libc`:

| Cặp | Brief ghi | Đo được | Gộp ở ngưỡng 0.6? |
|---|---|---|---|
| "Định luật Newton 1" / "Định luật Newton 2" | 0.89 | **0.8095** | có (đúng như đã biết) |
| khúc xạ / phản xạ | 0.677 | **0.2308** | **KHÔNG** |
| "Định luật Ohm" / "Định luật Newton 2" | 0.636 | **0.4348** | **KHÔNG** |

Chỉ 1/3 evidence point tái hiện. Nguyên nhân chưa xác định — nghi do khác
collation/provider hoặc khác phiên bản Postgres so với cluster lần trước.
**Chưa chỉnh ngưỡng.** Test khoá số đo thật; nếu đổi cluster mà test đỏ thì
đó là tín hiệu môi trường đổi, không phải code hỏng.

## Nợ kỹ thuật đã ghi nhận
- `find_candidates` dùng `similarity()` chứ không dùng toán tử `%`, nên **không
  dùng GIN index**. Đổi lại: ngưỡng không phụ thuộc GUC `pg_trgm.similarity_threshold`
  của session. Chấp nhận được ở quy mô một người dùng.

## Bẫy vận hành — đừng lặp lại
1. **`fish` không có `export`.** Truyền biến bằng `env VAR=value command`.
2. **Trước khi kill tiến trình `ks serve`:** xác nhận
   `systemctl --user show chiron-ks-http.service -p MainPID`. Đã có lần SIGKILL
   nhầm service production hai lần vì phán đoán "orphan" chỉ dựa vào `lsof`/port.
3. **Sửa code xong, systemd vẫn chạy code cũ** cho tới khi `systemctl restart`.
4. Postgres mặc định `unix_socket_directories = '/run/postgresql'` → user thường
   gặp `FATAL: could not create lock file`. Sửa thành PGDATA.
5. Port là **5432** (mặc định `initdb`). Nếu thấy `55432` ở đâu đó, đó là cluster
   của lần build trước — không dùng lại.
