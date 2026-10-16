# Hướng Dẫn Tích Hợp StreamingTTS Cho Zephyr Server (Client Integration Guide)

Tài liệu này cung cấp hướng dẫn đầy đủ cách tích hợp hệ thống **StreamingTTS-v8** (`POST /v1/audio/speech`) vào **Zephyr Server** và các dịch vụ Voicebot, AI Assistant, Trợ giảng tiếng Anh tương tác thời gian thực.

---

## 1. Tổng Quan Kiến Trúc StreamingTTS-v8

Phiên bản **StreamingTTS-v8** (Port **13128**) hoạt động theo cơ chế **Dual OmniVoice**:

1. **VietTTS (`VietTTS`)**: Sử dụng trọng số OmniVoice đã được fine-tune chuyên sâu trên kho ngữ liệu tiếng Việt, thể hiện ngữ điệu tự nhiên, chuẩn dấu thanh điệu (huyền, sắc, hỏi, ngã, nặng).
2. **EngTTS (`EngTTS`)**: Sử dụng trọng số OmniVoice bản gốc từ `k2-fsa/OmniVoice`, phát âm chuẩn bản ngữ quốc tế, giữ trọn vẹn ending sounds và nối âm tự nhiên.
3. **Chuẩn hóa giọng theo vùng miền (`north` & `south`)**:
   * Không còn sử dụng các tham số cũ (`vi_fe`, `en_ma`...).
   * Toàn bộ hệ thống được quy chuẩn về **vùng miền**: Giọng Bắc (`north`) và Giọng Nam (`south`).
4. **Không độ trễ khi đổi ngôn ngữ (Zero-Switching Latency)**: Cả 2 engine đều thường trực trên GPU VRAM, client có thể gọi xen kẽ tiếng Việt và tiếng Anh liên tục trong cùng 1 phiên mà không cần chờ nạp lại mô hình.

---

## 2. Thông Tin Kết Nối API

* **Base URL**: `http://<TTS_SERVER_IP>:13128`
* **Speech Endpoint**: `POST /v1/audio/speech`
* **Health Check**: `GET /v1/health` hoặc `GET /health`
* **Danh sách giọng**: `GET /voices`
* **Headers bắt buộc**:
  ```http
  Authorization: Bearer ioit2025
  Content-Type: application/json
  ```
  *(Token `ioit2025` là giá trị mặc định, có thể cấu hình thông qua biến môi trường `TTS_API_KEY`).*

---

## 3. Bảng Đặc Tả Tham Số Giọng Đọc (Voice Catalog)

Client có thể truyền tham số `voice` linh hoạt theo các cách dưới đây:

### 3.1. Bảng quy đổi tham số giọng

| Tham số `voice` | Ngôn ngữ | Vùng miền | Engine / Model | File mẫu conditioning | Mục đích sử dụng |
| :--- | :---: | :---: | :---: | :--- | :--- |
| **`north`** *(Khuyên dùng)* | Tự động | **Bắc** | Tự động nhận diện | `vietnamese_north.wav` / `english_north.wav` | Dùng cho văn bản tiếng Việt hoặc tiếng Anh giọng miền Bắc. |
| **`south`** *(Khuyên dùng)* | Tự động | **Nam** | Tự động nhận diện | `vietnamese_south.wav` / `english_south.wav` | Dùng cho văn bản tiếng Việt hoặc tiếng Anh giọng miền Nam. |
| **`vi_north`** | Tiếng Việt | **Bắc** | `VietTTS` | `voices/vietnamese_north.wav` | Giọng đọc tiếng Việt âm sắc chuẩn miền Bắc. |
| **`vi_south`** | Tiếng Việt | **Nam** | `VietTTS` | `voices/vietnamese_south.wav` | Giọng đọc tiếng Việt âm sắc truyền cảm miền Nam. |
| **`en_north`** | Tiếng Anh | **North** | `EngTTS` | `voices/english_north.wav` | Tiếng Anh bản ngữ chuẩn phong cách North. |
| **`en_south`** | Tiếng Anh | **South** | `EngTTS` | `voices/english_south.wav` | Tiếng Anh bản ngữ chuẩn phong cách South. |

> [!TIP]
> **Tương thích ngược (Backward Compatibility)**: Nếu các luồng cũ trên Zephyr Server vẫn gửi `vi_fe`, `vi_ma`, `en_fe`, `en_ma`, hệ thống v8 vẫn tự động tiếp nhận và chuyển hướng:
> * `vi_fe` $\rightarrow$ `vietnamese_south` | `vi_ma` $\rightarrow$ `vietnamese_north`
> * `en_fe` $\rightarrow$ `english_south` | `en_ma` $\rightarrow$ `english_north`

---

## 4. Đặc Tả Request Body (OpenAI Standard)

| Trường (Field) | Kiểu dữ liệu | Bắt buộc | Mặc định | Mô tả chi tiết |
| :--- | :---: | :---: | :---: | :--- |
| **`input`** | `string` | **Có** | - | Đoạn văn bản cần chuyển thành giọng nói (không để trống). |
| **`voice`** | `string` | Không | `"north"` | Giọng đọc: `"north"`, `"south"`, `"vi_north"`, `"vi_south"`, `"en_north"`, `"en_south"`. |
| **`model`** | `string` | Không | `"VietTTS"` | Tên model: `"VietTTS"` (cho tiếng Việt) hoặc `"EngTTS"` (cho tiếng Anh). |
| **`speed`** | `float` | Không | `1.0` | Tốc độ đọc (`0.25` – `4.0`):<br>• Luyện phát âm từ mới: nên đặt `0.8` – `0.85`.<br>• Giao tiếp tự nhiên: đặt `1.0`. |
| **`response_format`** | `string` | Không | `"wav"` | Định dạng file trả về: `"wav"`, `"mp3"`, `"pcm"`, `"opus"`, `"aac"`, `"flac"`. *(Khuyên dùng `"wav"` để đạt TTFB thấp nhất).* |
| **`colon_pause_seconds`** | `float` | Không | `0.2` | Khoảng lặng ngắt nghỉ vật lý (giây) tại vị trí dấu hai chấm `:`. |
| **`ellipsis_pause_seconds`**| `float` | Không | `0.4` | Khoảng lặng ngắt nghỉ vật lý (giây) tại vị trí dấu ba chấm `...`. |

---

## 5. Module Tích Hợp Chuẩn Cho Zephyr Server (Python SDK)

Dưới đây là module Python hoàn chỉnh được thiết kế sẵn để đặt trực tiếp vào mã nguồn của **Zephyr Server**. Module hỗ trợ đầy đủ các tác vụ: **Gọi (Call)**, **Tạo (Generate)** và **Lưu (Save/Cache)** file âm thanh.

```python
"""zephyr_tts_client.py
Module tích hợp StreamingTTS-v8 dành cho Zephyr Server.
Hỗ trợ cả cơ chế Synchronous (requests) và Asynchronous (httpx).
"""
import os
import time
import uuid
from pathlib import Path
from typing import Optional, Union, Literal
import requests
import httpx

# Cấu hình mặc định
DEFAULT_TTS_URL = os.getenv("TTS_SERVER_URL", "http://192.168.91.176:13128")
DEFAULT_TTS_KEY = os.getenv("TTS_API_KEY", "ioit2025")
DEFAULT_STORAGE_DIR = Path(os.getenv("TTS_AUDIO_STORAGE_DIR", "./audio_storage"))

VoiceType = Literal["north", "south", "vi_north", "vi_south", "en_north", "en_south"]
FormatType = Literal["wav", "mp3", "opus", "pcm"]


class ZephyrTTSClient:
    """Client kết nối StreamingTTS dành cho Zephyr Server."""

    def __init__(
        self,
        base_url: str = DEFAULT_TTS_URL,
        api_key: str = DEFAULT_TTS_KEY,
        storage_dir: Union[str, Path] = DEFAULT_STORAGE_DIR,
        timeout: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.speech_endpoint = f"{self.base_url}/v1/audio/speech"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _determine_model(self, voice: str, text: str) -> str:
        """Tự động xác định model VietTTS hoặc EngTTS nếu không khai báo rõ."""
        if voice.startswith("en") or voice.startswith("english"):
            return "EngTTS"
        if voice.startswith("vi") or voice.startswith("vietnamese"):
            return "VietTTS"
        # Với 'north' hoặc 'south': kiểm tra dấu tiếng Việt
        vi_accents = "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđĐ"
        is_vietnamese = any(c in vi_accents for c in text.lower())
        return "VietTTS" if is_vietnamese else "EngTTS"

    # -----------------------------------------------------------------------
    # 1. Cơ Chế Gọi & Nhận Dữ Liệu Bộ Nhớ (In-Memory Bytes)
    # -----------------------------------------------------------------------
    def synthesize_bytes(
        self,
        text: str,
        voice: VoiceType = "north",
        speed: float = 1.0,
        response_format: FormatType = "wav",
        colon_pause_seconds: Optional[float] = None,
        ellipsis_pause_seconds: Optional[float] = None,
    ) -> bytes:
        """Gửi yêu cầu tổng hợp âm thanh và nhận về raw bytes trong RAM."""
        model = self._determine_model(voice, text)
        payload = {
            "model": model,
            "input": text.strip(),
            "voice": voice,
            "speed": speed,
            "response_format": response_format,
        }
        if colon_pause_seconds is not None:
            payload["colon_pause_seconds"] = colon_pause_seconds
        if ellipsis_pause_seconds is not None:
            payload["ellipsis_pause_seconds"] = ellipsis_pause_seconds

        response = requests.post(
            self.speech_endpoint,
            headers=self.headers,
            json=payload,
            timeout=self.timeout,
        )
        if response.status_code != 200:
            raise RuntimeError(f"TTS API Error [{response.status_code}]: {response.text}")
        return response.content

    # -----------------------------------------------------------------------
    # 2. Cơ Chế Tạo & Lưu Trực Tiếp Thành File (Save to Storage)
    # -----------------------------------------------------------------------
    def synthesize_to_file(
        self,
        text: str,
        voice: VoiceType = "north",
        speed: float = 1.0,
        response_format: FormatType = "wav",
        output_filename: Optional[str] = None,
    ) -> Path:
        """Tổng hợp âm thanh và lưu trực tiếp ra file trên ổ đĩa."""
        audio_data = self.synthesize_bytes(
            text=text,
            voice=voice,
            speed=speed,
            response_format=response_format,
        )

        if not output_filename:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            short_id = uuid.uuid4().hex[:6]
            output_filename = f"tts_{voice}_{timestamp}_{short_id}.{response_format}"

        file_path = self.storage_dir / output_filename
        with open(file_path, "wb") as f:
            f.write(audio_data)

        return file_path

    # -----------------------------------------------------------------------
    # 3. Cơ Chế Asynchronous (Dành cho FastAPI / Voicebot Async của Zephyr)
    # -----------------------------------------------------------------------
    async def async_synthesize_bytes(
        self,
        client: httpx.AsyncClient,
        text: str,
        voice: VoiceType = "north",
        speed: float = 1.0,
        response_format: FormatType = "wav",
    ) -> bytes:
        """Gọi TTS bất đồng bộ (non-blocking) qua httpx."""
        model = self._determine_model(voice, text)
        payload = {
            "model": model,
            "input": text.strip(),
            "voice": voice,
            "speed": speed,
            "response_format": response_format,
        }
        resp = await client.post(
            self.speech_endpoint,
            headers=self.headers,
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.content
```

---

## 6. Kịch Bản Tích Hợp Tiêu Biểu Cho Zephyr Server

### Kịch bản 1: Luồng Học Tiếng Anh Tương Tác (English Learning Flow)

Trong các bài học, trợ lý Zephyr chuyển tiếp giữa hướng dẫn tiếng Việt và phát âm tiếng Anh:

```python
from zephyr_tts_client import ZephyrTTSClient

client = ZephyrTTSClient()

# Bước 1: Trợ giảng Việt hướng dẫn (Giọng Bắc hoặc Nam)
audio_step1 = client.synthesize_to_file(
    text="Bây giờ chúng ta sẽ cùng luyện phát âm từ vựng này nhé. Hãy chú ý âm đuôi:",
    voice="north",       # Giọng Bắc tiếng Việt
    speed=1.0,
    output_filename="lesson_01_intro.wav"
)

# Bước 2: Phát âm từ vựng mẫu (Tốc độ chậm để học viên bắt chước âm vị)
audio_step2 = client.synthesize_to_file(
    text="The oyster has a beautiful pearl.",
    voice="en_north",    # Tiếng Anh chuẩn bản ngữ
    speed=0.85,          # Giảm tốc độ để nghe rõ ending sounds
    output_filename="lesson_02_vocab_slow.wav"
)

# Bước 3: Đọc mẫu tốc độ giao tiếp tự nhiên
audio_step3 = client.synthesize_to_file(
    text="The oyster has a beautiful pearl.",
    voice="en_north",
    speed=1.0,           # Tốc độ thực tế
    output_filename="lesson_03_vocab_normal.wav"
)

# Bước 4: Nhận xét kết quả của học viên (Giọng miền Nam)
audio_step4 = client.synthesize_to_file(
    text="Giỏi lắm! Bạn đã phát âm rất chính xác và tự nhiên.",
    voice="south",       # Giọng Nam tiếng Việt
    speed=1.0,
    output_filename="lesson_04_feedback.wav"
)
```

---

### Kịch bản 2: Voicebot Tự Động Thích Ứng Vùng Miền (Dialect-Adaptive Bot)

Zephyr Server có thể chọn vùng miền dựa theo địa phương của người dùng:

```python
def answer_user(user_region: str, answer_text: str):
    # Ánh xạ theo khu vực của người dùng
    voice_choice = "south" if user_region.lower() in ("hcm", "south", "can_tho") else "north"
    
    # Tạo âm thanh phản hồi
    audio_bytes = client.synthesize_bytes(
        text=answer_text,
        voice=voice_choice,
        speed=1.0,
        response_format="wav"
    )
    return audio_bytes
```

---

## 7. Hướng Dẫn Điều Khiển Ngắt Nghỉ Vật Lý (Pause Control)

Để bài giảng hoặc câu nói tự nhiên, Zephyr Server có thể chèn các ký tự ngắt nghỉ:

* **Dấu hai chấm `:` (giới thiệu/dẫn dắt)**: Tự động ngắt nghỉ `0.2` giây (có thể chỉnh qua `colon_pause_seconds`).
  ```text
  "Từ vựng tiếp theo là: butterfly."
  ```
* **Dấu ba chấm `...` (chờ học viên trả lời hoặc nhấn nhá)**: Tự động ngắt nghỉ `0.4` giây (có thể chỉnh qua `ellipsis_pause_seconds`).
  ```text
  "Hãy sẵn sàng... bắt đầu nào!"
  ```

---

## 8. Những Lưu Ý Quan Trọng (Best Practices)

1. **Tách riêng câu tiếng Việt và tiếng Anh**:
   * *Không nên gộp chung*: `"Hãy đọc từ này: beautiful flower."` vào một request duy nhất.
   * *Nên tách*: Request 1 tiếng Việt (`"Hãy đọc từ này:"` $\rightarrow$ `voice="north"`), Request 2 tiếng Anh (`"beautiful flower."` $\rightarrow$ `voice="en_north"`).
2. **Định dạng file trả về**:
   * Nên ưu tiên `"response_format": "wav"` vì server render trực tiếp trên bộ nhớ đệm (RAM/VRAM), đem lại độ trễ phản hồi (Time To First Byte - TTFB) ngắn nhất (~150ms - 300ms).
3. **Quản lý Cache trên Zephyr Server**:
   * Đối với các câu nói cố định (lời chào, câu lệnh mẫu, lời khen), Zephyr Server nên lưu file `.wav` vào bộ nhớ đệm hoặc CDN theo khóa `hash(text + voice + speed)` để tái sử dụng ngay lập tức mà không cần gọi lại TTS server.
