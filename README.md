# Knowledge Store

"Second brain" lưu khái niệm học sinh đã học, thuộc hệ sinh thái Chiron.
Python + Postgres. Consumer duy nhất hiện tại là **Mnemosyne** (Socratic Coach,
Rust/Actix) — runtime khác nên giao tiếp bắt buộc qua HTTP.

- Horae **KHÔNG** ghi vào đây. LexiFlash hoãn có chủ đích.
- Node = một **khái niệm** ("Định luật Newton 2"), không phải một phiên học.
- Đọc [NOTES.md](NOTES.md) trước khi đổi bất cứ quyết định thiết kế nào.

## Cài đặt

```bash
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
cp .env.example .env    # rồi điền giá trị thật
```

`KS_HTTP_TOKEN` **phải là ASCII** — xem NOTES.md.

## Chạy

`fish` không có `export`. Truyền biến bằng `env VAR=value command` — cách này
hoạt động với mọi shell và mô phỏng đúng cách systemd gọi lệnh.

```bash
env KS_DATABASE_URL=postgresql://postgres@127.0.0.1:5432/chiron_ks .venv/bin/python -m ks.cli migrate
```

## CLI

| Lệnh | Việc |
|---|---|
| `migrate` | Chạy migration chưa áp dụng |
| `create-node` | Tạo khái niệm (qua dò trùng) |
| `suggest-edges --node-id` | Top-K ứng viên → LLM → cạnh `pending` |
| `list-pending` / `approve` / `reject` / `edit` | Duyệt cạnh |
| `add-edge` | Tự thêm cạnh (vào thẳng `approved`) |
| `neighbors --node-id` | Node kề qua cạnh đã approved |
| `stats` | Số liệu instrumentation |
| `save-transcript --session-ref --file` | Lưu transcript raw (không chạm LLM) |
| `extract` | Rút khái niệm từ transcript chờ xử lý |
| `list-extracted` / `accept` / `discard` | Xác nhận khái niệm đã rút |
| `serve` | Chạy HTTP server (block vô hạn) |

## HTTP API

Auth: `Authorization: Bearer <KS_HTTP_TOKEN>`. `/health` không cần auth.

| Route | Ghi chú |
|---|---|
| `GET /health` | Liveness thuần, không chạm DB |
| `POST /transcripts` | `{session_ref, content}`. Idempotent thật theo `session_ref`. Không trigger extraction. `ok:false` + HTTP 200 = KS sống, DB chết |
| `POST /ingest` | `{drafts:[...]}`. All-or-nothing. `psycopg.Error` → 503. Idempotency là **fuzzy match theo similarity**, không phải khoá định danh — retry an toàn chỉ khi giữ nguyên văn `title` |
| `GET /nodes` | `?subject=&source_module=&limit=` (mặc định 50, **trần 500**, vượt trần → 400 chứ không âm thầm cắt). Không trả edges |

## Test

```bash
env KS_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5432/chiron_ks_test .venv/bin/python -m pytest -q
```

Test chạy trên Postgres **thật** — trigram là hành vi của Postgres, mock nó thì
test mất hết giá trị.

## Vận hành (systemd user units)

File unit ở [deploy/](deploy/). Cài:

```bash
cp deploy/*.service deploy/*.timer ~/.config/systemd/user/ && systemctl --user daemon-reload
```

| Unit | Vai trò |
|---|---|
| `chiron-ks-postgres.service` | Cụm Postgres riêng, port 5432 |
| `chiron-ks-http.service` | `ks serve`, `Type=simple` (block vô hạn, không phải cron) |
| `chiron-ks-extract.timer` | Mỗi 30 phút. **Cần `DEEPSEEK_API_KEY`** |
| `chiron-ks-stats.timer` | 23:00 hằng ngày |

Sửa code xong phải `systemctl --user restart chiron-ks-http` — không restart thì
curl vẫn đang test code cũ.

Trước khi kill bất kỳ tiến trình `ks serve` nào, xác nhận
`systemctl --user show chiron-ks-http.service -p MainPID`. Đừng phán đoán
"orphan" chỉ dựa vào `lsof`/port.
