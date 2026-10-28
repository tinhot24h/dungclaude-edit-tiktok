# ai33.pro API contract used by Review Studio

Source: API documentation screenshots supplied by the user in this conversation; original page https://ai33.pro/app/api-document. The cloud network blocked reading that page directly. No API key was included in the screenshots or copied into code.

Base URL: `https://api.ai33.pro`. Authentication: `xi-api-key: <key>`. TLS verification stays enabled.

## Text To Speech v3

`POST /v3/text-to-speech`, **multipart/form-data**, not JSON.

- `text`: required, max 1,000,000 characters.
- `voice_id`: required and already prefixed with `elevenlabs_`, `minimax_`, `clone_`, `edge_`, `kokoro_`, `vbee_` or `fishaudio_`.
- `speed`: 0.5–1.5, default 1.
- `with_transcript`: boolean, default false; Review Studio currently sends false.
- `file_name`: optional provider output name suggestion.
- `pronunciation_dictionary_id`: optional positive integer of an existing dictionary.
- `receive_url`: optional webhook; intentionally omitted because this local app polls instead.

Create success: `{"success":true,"task_id":"uuid_task_id"}`. A create request is sent once. Network failure/timeout does not cause an automatic retry.

## Voice Library v3

`GET /v3/voices?provider=edge&language=Vietnamese&gender=Female&page=1&page_size=30`

Provider required: `elevenlabs|minimax|clone|edge|kokoro|vbee|fishaudio`. Search uses `search`; language/gender optional. Page size default 30, max 100. Returned voice IDs are used directly without adding another prefix.

Response: `success`, `data:[{voice_id,name,language,gender,tags,preview_url}]`, `pagination:{page,page_size,total,has_more}`. Example ID in the supplied documentation: `edge_vi-VN-HoaiMyNeural`.

## Common v1

- `GET /v1/task/{task_id}` → direct task object containing `id,status,progress,error_message,credit_cost,metadata,type`. Status `doing|done|error`; stop polling at done/error. Audio location is **`metadata.audio_url`**. Other optional outputs `metadata.srt_url` and `metadata.json_url` are not used in this release.
- `GET /v1/tasks?page=1&limit=20` → `success,data,page,limit,total`. Type filter exists but this release reads recent history without restricting provider-specific task type names.
- `GET /v1/credits` → `{"success":true,"credits":123}`.

The API also documents task deletion/refunds, dialogue, cloning, dictionary CRUD and health checks. These are outside this single-voice TTS integration. Existing cloned voices can be chosen from the voice library; the app does not create clones or delete tasks.

## Local integration behavior

Keys stay in the password field for the session or server environment (`REVIEW_AI33_KEY` / `AI33_API_KEY`). They never go into localStorage, files, the ZIP, query strings or media/CDN requests. Provider errors are summarized without echoing raw request details.

The task ID and text can be retained in browser storage. Polling runs every 5 seconds, stopping on error/done or after 15 minutes of tracking; stopping polling does not cancel provider processing. A saved task can be checked again without re-creating it.

Completed audio is fetched only from the authenticated task response, via public HTTPS with TLS verification and public-address checks, no `xi-api-key` forwarded. Redirects receive the same address checks. Source downloads capped at 100 MB / a bounded timeout. Only supported audio signatures (MP3/WAV/FLAC/Ogg/M4A) reach FFmpeg; playlists are rejected. FFmpeg input protocols are limited to file/pipe; output is MP3 (`libmp3lame`, 192 kbps).

MP3 files are validated with FFprobe and cached under `.local/audio/<task-hash>.mp3`. Existing valid cached files are reused without another provider request. Local playback supports byte ranges and download, without requiring a key for the already cached file. No remote audio URL or API key is persisted in that cache.

## Validation boundaries

Unit tests use HTTP response fixtures matching the screenshots. A separate local integration harness simulated provider responses while exercising real FFmpeg conversion and browser MP3 playback/download/range handling. No live ai33.pro calls or billed synthesis were made: the environment has no ai33 key and its current network policy blocks the provider host. The first real synthesis needs a user-supplied key in the app and provider credits/permissions.

## Thay đổi 0.7

Thư viện giọng tự tải nhiều trang (100 giọng/trang yêu cầu, tôn trọng page_size trả về, dừng khi trang trống). Giữ file_name đã gửi cùng task_id trong catalog cục bộ; không lưu key/link có chữ ký. MP3 có thể chọn sang trình dựng hoặc nhập thủ công.

Download gửi Accept audio, User-Agent và Referer ai33; giữ xác minh TLS và proxy. Lỗi HTTP có mã AUDIO_HTTP_*, TLS/mạng/định dạng được tách riêng. Khi done, UI cung cấp link gốc từ tác vụ xác thực để người dùng mở bằng trình duyệt và nhập file; không tạo lại TTS. Chưa chứng minh nguyên nhân lỗi tải thật nếu chưa có phản hồi CDN của tài khoản.

## Thay đổi 0.8

Key input tự tải giọng/lịch sử sau debounce 800 ms hoặc blur. Phản hồi cũ khi đổi tài khoản bị bỏ qua. Lịch sử cập nhật theo trang hiện tại mỗi 30 giây khi tab audio đang hiển thị, sau tạo và cache audio. Không tự tải hàng loạt file hoặc gửi TTS mới.

## Thay đổi 0.9.2 — đủ bộ API v3 theo tài liệu người dùng cung cấp

- **Text To Dialogue** `POST /v3/text-to-speech/dialogue` (multipart): `text` dùng nhãn `A>`, `B>`…, `speakers` là JSON `[{voice_id,speed}]` (tối thiểu 2, ánh xạ theo thứ tự), `delay` 0–5 giây, `with_transcript` chỉ ở cấp trên cùng, `file_name`, `pronunciation_dictionary_id`. Ứng dụng kiểm tra nhãn trong văn bản không vượt số người nói.
- **Pronunciation Dictionary** `GET/POST /v3/dictionaries`, `PUT/DELETE /v3/dictionaries/:id`, `POST /v3/dictionaries/preview` (JSON). Quy tắc `{from,to,matchType:word|contains,caseSensitive}`; `id` trả về dùng làm `pronunciation_dictionary_id`.
- **Clone Voice** `POST /v3/text-to-speech/voice-clone` (multipart `voice_name`, `audio_file` ≤ 10 MB) → `data.voice_id`, dùng dạng `clone_<id>`. **Delete Clone Voice** `DELETE /v3/text-to-speech/voice-clone/:id`.
- **Voice Library** thêm bộ lọc `tags, locale, age, accent, category, use_case, descriptive`, riêng vbee `voice_ownership`, riêng fishaudio `sort`, `tag`.
- **Phụ đề**: khi bật `with_transcript`, `metadata.srt_url` của tác vụ được tải qua cùng kiểm tra HTTPS/địa chỉ công khai như audio và trả về file `.srt` cho người dùng; không lưu link có chữ ký.
- Không gửi `receive_url` (ứng dụng cục bộ dùng polling `GET /v1/task/:id`).

## Dubbing v1 (timestamp mode, from the user's documentation screenshots)

`POST /v1/task/dubbing`, multipart: `file` (audio.mp3 or audio.m4a), `num_speakers` (0 = auto), `disable_voice_cloning`,
`source_lang` (`auto`, `zh`, `en`…), `target_lang`, optional `voice_id` (v3 prefixed, Kokoro not supported), `receive_url`
(required). Review Studio polls `GET /v1/task/{id}` instead of a webhook and sends a reserved `.invalid` callback address,
so the result payload is delivered nowhere. Done task metadata: `audio_url` (default dubbed audio, keeps the original
background), `srt_url` (translated SRT), `replacement_audio_url` (voice-only track synthesized from the SRT with
`voice_id`, +25% credits), `replacement_status`. The app uses the replacement track over its own separated background, and
falls back to the default track (without adding the background again) when the replacement failed.
