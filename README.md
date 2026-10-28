# StreamingTTS — Dual OmniVoice TTS Server

Server chuyển văn bản thành giọng nói tiếng Việt và tiếng Anh, API tương thích OpenAI (`POST /v1/audio/speech`). Chạy trong Docker trên GPU server, cổng **13128**. Client chính là zephyl-server: server đó tự cắt câu trả lời của LLM thành từng đoạn và gọi TTS cho từng đoạn.

Đây là tài liệu duy nhất của dự án: kiến trúc, giọng đọc, API, cấu hình, triển khai và log.

---

## 1. Kiến trúc

| Thành phần | Vai trò |
|---|---|
| **VietTTS** (`models/viettts`) | OmniVoice fine-tune tiếng Việt, clone giọng từ file mẫu trong `voices/` |
| **EngTTS** (`models/engtts`) | OmniVoice pretrained gốc (k2-fsa) cho tiếng Anh. Khi cùng GPU với VietTTS thì dùng chung `audio_tokenizer` (tiết kiệm khoảng 768 MB VRAM). |
| **TextNormalizer** (`models/normalizer`) | Chuẩn hoá văn bản tiếng Việt: luật regex + CRF (`soe-vinorm`), đọc số, ngày, giờ, tiền tệ, viết tắt. Chỉ áp dụng cho VietTTS. |
| **Hậu xử lý** | `sox tempo` (tốc độ), tăng âm lượng (`tanh`), giới hạn peak, chèn khoảng lặng sau `:` và `...`, encode WAV/PCM, ffmpeg cho mp3/opus/aac/flac |

Luồng xử lý một request:

```
request -> auth -> chọn voice -> normalize (chỉ VI) -> tách đoạn theo ":" / "..."
        -> OmniVoice.generate() từng đoạn -> tempo / loudness -> ghép + khoảng lặng
        -> limit_peak -> encode -> response
```

Hai model được nạp sẵn lên GPU lúc khởi động, kèm prompt clone của 6 giọng và warmup. `TTS_MAX_WORKERS=1` (mặc định), nên các request được xử lý tuần tự trên GPU.

## 2. Cấu trúc thư mục

```
app/             FastAPI app (main.py), auth, schemas, hậu xử lý audio, CSV logger
config/          settings.py: toàn bộ cấu hình (override bằng env) + VOICE_MAP
engines/         viettts/ và engtts/: wrapper quanh OmniVoice
text_normalizer/ chuẩn hoá văn bản tiếng Việt
voices/          file mẫu clone giọng: <tên>.wav + <tên>.txt (transcript)
models/          weights (không có trong git)
Dockerfile       image tự build từ ubuntu:22.04, đóng gói sẵn thư viện + model + code
requirements.txt thư viện cần cài; constraints.txt pin đúng version đang chạy
run.sh           (server) build + chạy container `streamingtts`
sync_to_server.sh, test_13128.sh   (Mac) đồng bộ lên server / test API
```

## 3. Giọng đọc

| Giọng chuẩn | Engine | Alias được chấp nhận |
|---|---|---|
| `vietnamese_north` | VietTTS | `north`*, `vi_north`, `vi_ma` |
| `vietnamese_south` | VietTTS | `south`*, `vi_south`, `vi_fe` |
| `ai_calling_vi` | VietTTS | `ai_calling`*, `vi_ai_calling` |
| `english_north` | EngTTS | `en_north`, `en_ma` |
| `english_south` | EngTTS | `en_south`, `en_fe` |
| `ai_calling_en` | EngTTS | `en_ai_calling` |

\* `north`, `south`, `ai_calling` được chọn theo trường `model`: `model="EngTTS"` thì dùng bản tiếng Anh, còn lại dùng bản tiếng Việt.

Thêm giọng mới:
1. Đặt `<tên>.wav` (khoảng 5–10 giây, sạch) và `<tên>.txt` (đúng lời đọc) vào `voices/`.
2. Gọi `register_voice()` trong `_load_all()` ở [app/main.py](app/main.py).
3. Thêm mục vào `VOICE_MAP` trong [config/settings.py](config/settings.py).

## 4. API

**`POST /v1/audio/speech`**, header `Authorization: Bearer <TTS_API_KEY>`

| Trường | Mặc định | Ghi chú |
|---|---|---|
| `model` | `VietTTS` | `VietTTS` / `EngTTS` |
| `input` | (bắt buộc) | Văn bản cần đọc |
| `voice` | `north` | Xem mục 3 |
| `response_format` | `wav` | `wav`, `pcm` (int16, 24 kHz mono), `mp3`, `opus`, `aac`, `flac` |
| `speed` | `1.0` | 0.25–4.0. VietTTS còn nhân thêm `TTS_VIETTTS_TEMPO`. |
| `pause_seconds` | — | Khoảng lặng chung cho cả `:` và `...` |
| `colon_pause_seconds` | 0.2 | Khoảng lặng sau `:` |
| `ellipsis_pause_seconds` | 0.4 | Khoảng lặng sau `...` |
| `num_step` | tự động | 4–100. Mặc định: 14 step cho chuỗi ≤ 8 ký tự, các trường hợp khác 46 step. |

Response trả về audio nhị phân, kèm header `X-Request-ID`.

Mã lỗi (body dạng `{"detail": {"error": {"code": ..., "message": ...}}}`):

| HTTP | `code` | Khi nào |
|---|---|---|
| 400 | `invalid_input` / `invalid_voice` / `invalid_format` | `input` rỗng, voice không tồn tại, định dạng không hỗ trợ |
| 401 | `invalid_api_key` | Sai Bearer token |
| 422 | `empty_audio` | Model không sinh được audio cho đoạn văn bản |
| 500 | `synthesis_error` / `internal_error` | Lỗi khi tổng hợp (traceback trong `errors-*.log`) |

**`GET /voices`**: danh sách giọng theo model. **`GET /health`**: trạng thái server (không cần token; không có `/v1/health`).

Lưu ý cho client:
- Server xử lý tuần tự trên GPU. Gửi từng đoạn ngắn (một hoặc vài câu) để độ trễ mỗi đoạn thấp.
- `:` và `...` trong `input` tạo khoảng lặng thật trong audio, điều chỉnh bằng `colon_pause_seconds` / `ellipsis_pause_seconds`.
- Chỉ VietTTS chuẩn hoá số, ngày, giờ, tiền tệ. Với EngTTS, client nên viết số thành chữ.

```bash
curl -X POST http://<SERVER_IP>:13128/v1/audio/speech \
  -H "Authorization: Bearer ioit2025" -H "Content-Type: application/json" \
  -d '{"model":"VietTTS","input":"Xin chào, tôi là trợ lý ảo.","voice":"ai_calling"}' \
  -o out.wav
```

## 5. Cấu hình chính (biến môi trường)

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `TTS_API_KEY` | `ioit2025` | Bearer token |
| `TTS_DEVICE` | `cuda:0` | GPU mặc định cho cả hai engine |
| `TTS_VIETTTS_DEVICE` / `TTS_ENGTTS_DEVICE` | theo `TTS_DEVICE` | Đặt riêng GPU cho từng engine |
| `TTS_VIETTTS_NUM_STEP` / `TTS_ENGTTS_NUM_STEP` | `46` | Số step diffusion cho câu thường |
| `TTS_*_NUM_STEP_SHORT`, `TTS_*_SHORT_THRESHOLD` | `14`, `8` | Số step cho chuỗi rất ngắn |
| `TTS_*_AUDIO_CHUNK_DURATION` / `_THRESHOLD` | `10.0` / `15.0` | Cắt chunk khi văn bản dài |
| `TTS_VIETTTS_TEMPO` | `1.1` | Hệ số tốc độ nền của VietTTS |
| `TTS_ENGTTS_VOLUME_BOOST` / `TTS_VIETTTS_VOLUME_BOOST` | `1.5` / `1.0` | Tăng âm lượng |
| `TTS_COLON_PAUSE_SECONDS` / `TTS_ELLIPSIS_PAUSE_SECONDS` | `0.2` / `0.4` | Khoảng lặng mặc định |
| `TTS_OUTPUT_PEAK_DBFS` | `-1.0` | Ngưỡng peak đầu ra |
| `TTS_VIETTTS_TORCH_COMPILE` | `0` | Bật `torch.compile` (có rủi ro lẫn sang tiếng Anh giữa câu) |
| `TTS_MAX_WORKERS` | `1` | **Giữ 1**: engine chưa an toàn khi chạy song song |

Xem đầy đủ trong [config/settings.py](config/settings.py).

## 6. Triển khai

Image `streamingtts:latest` tự build từ `ubuntu:22.04`, **không phụ thuộc image riêng nào**:
- Thư viện được pin qua `constraints.txt`.
- PyTorch cu128 tự mang theo CUDA, server chỉ cần NVIDIA driver (≥ 570) và NVIDIA Container Toolkit.
- Model được **đóng gói vào image** lúc build (mỗi model một layer, đặt trước code nên sửa code build lại vẫn nhanh). Khi chạy chỉ mount `logs/`.
- Image khoảng 14 GB, chạy được ở bất kỳ đâu chỉ với một file: `docker save streamingtts:latest | gzip > streamingtts.tar.gz`, sang máy khác thì `gunzip -c streamingtts.tar.gz | docker load`.
- Thư mục `models/` vẫn cần có trên server để build.

Để dựng lại ở server khác, chỉ cần code trong git cộng thư mục `models/`.

```bash
# 1. Mac: đẩy code, voices và models lên ~/Desktop/Ominivoice-TTS trên server
./sync_to_server.sh

# 2. Server: build image và chạy container `streamingtts` (tham số là GPU id, mặc định 0)
cd ~/Desktop/Ominivoice-TTS && ./run.sh 0

# 3. Mac: test
./test_13128.sh "Xin chào, tôi là trợ lý ảo." ai_calling
./test_13128.sh "Hello, how can I help you?" en_south
```

Khi build ra image **khác** bản đang chạy, `run.sh` giữ bản cũ dưới tên `streamingtts:previous` (build lại mà không đổi gì thì giữ nguyên). Rollback:

```bash
docker tag streamingtts:previous streamingtts:latest && SKIP_BUILD=1 ./run.sh
```

Gắn tag phiên bản (tuỳ chọn): `docker tag streamingtts:latest streamingtts:<tên-tag>`.

### Dựng trên server mới

1. Cài NVIDIA driver (≥ 570), Docker và NVIDIA Container Toolkit theo hướng dẫn chính thức của NVIDIA. Kiểm tra bằng `docker run --rm --gpus all ubuntu nvidia-smi`.
2. Sửa `SERVER_USER`, `SERVER_IP`, `SERVER_PORT` trong [sync_to_server.sh](sync_to_server.sh), rồi chạy script từ Mac. Lần đầu sẽ chép khoảng 6.4 GB model.
3. Trên server: `cd ~/Desktop/Ominivoice-TTS && ./run.sh 0`. Lần build đầu cần internet để tải khoảng 3–4 GB thư viện.
4. Từ Mac: `BASE_URL=http://<IP_MỚI>:13128 ./test_13128.sh`.

## 7. Log

Thư mục `logs/` (trên server: `~/Desktop/Ominivoice-TTS/logs`) chứa:
- `requests-YYYY-MM-DD.csv`: mỗi request một dòng, gồm voice, văn bản gốc và văn bản đã chuẩn hoá, status, `ttfb_ms` (thực chất là tổng thời gian xử lý), số byte đầu ra.
- `errors-YYYY-MM-DD.log`: traceback khi có lỗi.

Log tự xoá sau 30 ngày, thời gian theo UTC+7.
