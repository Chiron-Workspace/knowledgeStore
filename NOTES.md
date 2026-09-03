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

### Ba evidence point — đã truy lại được, môi trường KHÔNG đổi
Đo trên PostgreSQL 18.6, pg_trgm 1.6, collation `en_US.UTF-8`, provider `libc`:

| Chuỗi A (nguyên văn) | Chuỗi B (nguyên văn) | similarity | Gộp ở 0.6? |
|---|---|---|---|
| `Định luật Newton 1` | `Định luật Newton 2` | 0.8095 | **có** |
| `Định luật khúc xạ ánh sáng` | `Định luật phản xạ ánh sáng` | 0.6774 | **có** |
| `Định luật Ohm (curl-nodes)` | `Định luật Newton 2 (curl-nodes)` | 0.6364 | **có** |
| `khúc xạ` | `phản xạ` | 0.2308 | không |
| `Định luật Ohm` | `Định luật Newton 2` | 0.4348 | không |

Cả ba evidence point của lần build trước đều tái hiện **chính xác** khi đo đúng
chuỗi (0.636 → 0.6364; 0.677 → 0.6774). Ban đầu tôi đo trên cặp title trần
(`khúc xạ` vs `phản xạ`, `Định luật Ohm` vs `Định luật Newton 2`) và kết luận
nhầm rằng môi trường đã đổi. **Không có khác biệt môi trường nào.** Giả thuyết
collation đã bị bác bỏ, không cần điều tra thêm.

Cơ chế: phần chung của hai chuỗi chiếm đa số trigram. Cùng tiền tố
`"Định luật "` cộng cùng hậu tố `" ánh sáng"` / `" (curl-nodes)"` đẩy similarity
từ 0.23 lên 0.68 dù phần khác biệt y hệt nhau. Hậu tố dùng chung là thứ nguy
hiểm nhất cho dedup trigram — và title thật từ Mnemosyne rất dễ có hậu tố chung
(tên chương, tên môn, tên bộ đề).

### QUY TẮC: cách ghi một evidence point
Ghi lại một con số mà không ghi chuỗi đầu vào chính xác thì **không tái sử dụng
được** — đó là bài học đắt nhất rút ra ở đây. Hai trong ba số cũ suýt bị diễn
giải thành "môi trường đã đổi" chỉ vì thiếu chuỗi gốc.

Từ nay mọi evidence point về dedup PHẢI ghi đủ:
1. **Nguyên văn cả hai chuỗi**, kể cả tiền tố/hậu tố trông như rác kỹ thuật
   (`(curl-nodes)` chính là thứ tạo ra con số).
2. `SELECT extversion FROM pg_extension WHERE extname = 'pg_trgm';`
3. `SELECT datcollate, datctype, datlocprovider FROM pg_database WHERE datname = current_database();`

Thiếu ba thứ này thì đến lúc quyết pgvector sẽ không biết số cũ nghĩa là gì.
`tests/test_dedup_limits.py` khoá cả ba bằng test, gồm cả dấu vân tay môi trường.

## Nợ kỹ thuật đã ghi nhận
- `find_candidates` dùng `similarity()` chứ không dùng toán tử `%`, nên **không
  dùng GIN index**. Đổi lại: ngưỡng không phụ thuộc GUC `pg_trgm.similarity_threshold`
  của session. Chấp nhận được ở quy mô một người dùng.

## deepseek-v4-flash là model REASONING — reasoning token tính vào max_tokens

Phát hiện khi chạy thật, không phải suy đoán. Một lần gọi gợi ý edge với 2 ứng viên:

```
completion_tokens: 222
  completion_tokens_details.reasoning_tokens: 158   ← 71% ngân sách
prompt_tokens: 474 (cached 384)
```

Lượng reasoning thay đổi mỗi lần chạy. Với `max_tokens=1000`, đã có lần reasoning
ngốn gần hết ngân sách và chỉ còn ~15 token cho JSON → phản hồi cụt giữa chừng:

```
[
  {
    "candidate": 0,
    "relation_type": "pr        ← hết token ở đây
```

Hai thứ đã sửa:
1. `EDGE_SUGGESTION_MAX_TOKENS` / `EXTRACTION_MAX_TOKENS` = **4000**. Đừng hạ hai
   số này theo độ dài output NHÌN THẤY được (~200 ký tự) — phần lớn ngân sách là
   reasoning vô hình. Chi phí chỉ tính theo token thực sinh ra; cắt ngang thì
   hỏng cả lô.
2. `LLMTruncatedError` (con của `LLMTransientError`) bắt `finish_reason == "length"`
   ở OpenAI-compatible và `stop_reason == "max_tokens"` ở Anthropic. Trước đó JSON
   cụt lọt xuống `json.loads` và hiện ra dưới dạng `LLMParseError` — chẩn đoán sai
   hoàn toàn, vì cấu trúc phản hồi không hề sai, nó chỉ chưa viết xong. Là lớp con
   của Transient nên retry được: cùng `max_tokens` lúc đủ lúc không.

Instrumentation đã ghi đúng sự cố này (`edge_suggestion_run.outcome = 'parse_error'`)
— đây chính là bằng chứng ràng buộc §7 có tác dụng thật.

## card_sync: nhánh `reason="truncated"` CHƯA VERIFY được trên dữ liệu thật

Bảng quyết định của `card_sync` xử lý sáu ca. Năm ca đã chạy thật với Mnemosyne
sống trên `127.0.0.1:8081`:

| Ca | Đã verify thật | Kết quả |
|---|---|---|
| 201 card mới | ✅ | `sent` |
| 409 card đã có | ✅ | `sent` (Mnemosyne check trước khi gọi LLM → không tốn token) |
| 404 set/node sai | ✅ | `skipped`, không retry |
| Không gọi nổi Mnemosyne | ✅ | dừng cả lô, `attempts` giữ nguyên |
| 503 KS chưa cấu hình | ❌ chỉ fake | `pending` |
| **502 `reason="truncated"`** | **❌ chỉ fake** | `failed`, không retry |

**`truncated` là nhánh đáng lo nhất và chưa từng chạy thật.** Mnemosyne tự xác
nhận họ cũng không ép được truncation thật qua integration test — fake provider
của họ phủ qua trait boundary. Nghĩa là logic "không retry nếu truncated" ở cả
hai phía đều dựa trên thiết kế hợp lý chứ chưa dựa trên dữ liệu thật.

Đây KHÔNG phải lỗi, chỉ là trung thực về phạm vi đã kiểm. Khi job gặp `truncated`
lần đầu ngoài đời, `ks.card_sync_log.last_error` giữ NGUYÊN VĂN `reason` +
message (không rút gọn) — đó là bằng chứng duy nhất để kiểm hành vi có đúng
thiết kế không. Tìm bằng:

```sql
SELECT * FROM ks.card_sync_log WHERE last_error LIKE '%truncated%';
```

Ghi chú liên quan: KS đã đo được `deepseek-v4-flash` là model reasoning và bị
cắt output thật (xem mục trên). Mnemosyne dùng cùng provider, nên `truncated`
gần như chắc chắn sẽ xảy ra — chỉ là chưa bắt được lúc nó xảy ra.

## Mnemosyne KHÔNG có systemd unit

`card_sync` phụ thuộc Mnemosyne sống ở `127.0.0.1:8081`, nhưng Mnemosyne chạy
thủ công bằng `cargo run -p backend` và không có unit systemd nào. Timer
`chiron-ks-card-sync.timer` chạy hằng giờ bất kể — khi Mnemosyne chết, job ghi
`pending` và KHÔNG đốt lượt retry, nên tick sau tự bù. Không mất dữ liệu, chỉ
trễ. Không cần sửa gì phía KS.

Mnemosyne cũng chưa có auth layer (simplification có chủ ý phía họ), nên
`KS_MNEMOSYNE_TOKEN` để trống được. KS vẫn gửi header `Authorization` NẾU biến
có giá trị, để sẵn sàng cho lúc họ thêm auth.

## LỆCH BRIEF CÓ CHỦ ĐÍCH: systemd ở mức USER, không phải system

Brief §10 và bản build lần trước dùng system-level (`/etc/systemd/system/`,
`sudo systemctl ...`). Lần này chốt **user-level** (`~/.config/systemd/user/`).

Hệ quả — mọi lệnh vận hành trong brief và tài liệu cũ đều phải thêm `--user`:

| Tài liệu cũ | Đúng cho bản này |
|---|---|
| `sudo systemctl status chiron-ks-http` | `systemctl --user status chiron-ks-http` |
| `sudo systemctl restart chiron-ks-http` | `systemctl --user restart chiron-ks-http` |
| `sudo journalctl -u chiron-ks-http` | `journalctl --user -u chiron-ks-http` |
| `sudo systemctl show ... -p MainPID` | `systemctl --user show ... -p MainPID` |

Đánh đổi đã cân nhắc:
- **Được:** không cần sudo mỗi lần sửa unit; unit chạy đúng dưới user `zinnn`,
  cùng user sở hữu PGDATA `~/.local/share/chiron-ks-postgres`, nên không phải
  khai báo `User=`/`Group=` hay lo quyền thư mục.
- **Mất:** cần `sudo loginctl enable-linger zinnn` (một lần) thì service mới
  sống qua logout và tự lên lúc boot. **Chưa chạy** — `Linger=no`. Không có
  linger thì KS chết khi logout và Mnemosyne mất endpoint.

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

## Phát hiện mới trong lần build này
**`KS_HTTP_TOKEN` bắt buộc phải là ASCII.** Đo bằng curl thật: token chứa tiếng
Việt làm MỌI request 403 vĩnh viễn. Nguyên nhân: WSGI giải mã giá trị header HTTP
bằng latin-1, nên byte UTF-8 của token tới tay ứng dụng dưới dạng mojibake và
không bao giờ khớp. Đây là lỗi CẤU HÌNH, không phải lỗi client — nên
`validate_token_config()` chạy lúc `ks serve` khởi động và chết ngay nếu token
non-ASCII, thay vì im lặng hỏng.

Khác với bug `hmac.compare_digest` (§9 của brief): bug đó là header CLIENT gửi lên
có ký tự non-ASCII làm crash 500; đã chặn bằng cách so trên bytes. Hai lỗi độc lập,
đều có test riêng.
