# Hướng Dẫn Tích Hợp TTS API Thời Gian Thực (Client Integration Guide)

Tài liệu này hướng dẫn chi tiết cách gọi và truyền tham số thời gian thực (realtime) tới hệ thống **StreamingTTS** (`POST /v1/audio/speech`), đặc biệt phục vụ cho các ứng dụng Voicebot, trợ lý ảo và **Tính năng Học Tiếng Anh (English Learning)**.

---

## 1. Cơ Chế Chuyển Đổi Ngôn Ngữ Realtime (Zero-Switching Latency)

* **Nạp sẵn đồng thời (Dual-Engine In-Memory)**: Cả hai động cơ **VietTTS** (OmniVoice tiếng Việt) và **EngTTS** (Kokoro tiếng Anh) đều được nạp sẵn và giữ ấm (warmup) thường trực trên RAM/VRAM ngay từ khi server khởi động.
* **Xử lý phi trạng thái (Stateless)**: Server không cần nạp lại model khi chuyển đổi giữa tiếng Việt và tiếng Anh.
* **Quyết định nhánh dựa trên `voice`**:
  * `voice="vi_fe"` hoặc `"vi_ma"` $\rightarrow$ Chạy qua pipeline chuẩn hóa tiếng Việt (`TextNormalizer`) và tổng hợp bằng **VietTTS**.
  * `voice="en_fe"` hoặc `"en_ma"` $\rightarrow$ Bỏ qua chuẩn hóa tiếng Việt và tổng hợp trực tiếp bằng **EngTTS**.
* **Đổi giọng linh hoạt giữa các câu**: Client có thể gửi câu 1 là tiếng Việt (`vi_fe`), câu 2 là tiếng Anh (`en_fe`), câu 3 là tiếng Việt (`vi_fe`) hoàn toàn liên tục mà **không có độ trễ chuyển đổi**.

---

## 2. Thông Tin Kết Nối API

* **Endpoint**: `POST http://<TTS_HOST>:<PORT>/v1/audio/speech`
  * Mặc định cục bộ: `http://localhost:13125/v1/audio/speech`
* **Headers bắt buộc**:
  ```http
  Authorization: Bearer ioit2025
  Content-Type: application/json
  ```
  *(Token `ioit2025` là giá trị mặc định, có thể thay đổi bằng biến môi trường `TTS_API_KEY` trên server).*

---

## 3. Bảng Đặc Tả Tham Số (Request Body)

Định dạng JSON gửi trong body theo chuẩn tương thích OpenAI:

| Tham số | Kiểu dữ liệu | Bắt buộc | Mặc định | Ý nghĩa & Hướng dẫn sử dụng |
| :--- | :---: | :---: | :---: | :--- |
| **`input`** | `string` | **Có** | - | Đoạn văn bản cần chuyển thành giọng nói (không được để trống). |
| **`voice`** | `string` | **Có** | `"vi_fe"` | **Quyết định ngôn ngữ và âm sắc giọng đọc**:<br>• `"vi_fe"`: Nữ miền Nam tiếng Việt (giọng mẫu chuẩn `south2.wav`).<br>• `"vi_ma"`: Nam tiếng Việt (giọng mẫu chuẩn `north1.wav`).<br>• `"en_fe"`: Nữ/Bé gái tiếng Anh bản xứ (`af_heart` + preset Praat `girl`).<br>• `"en_ma"`: Nam/Bé trai tiếng Anh bản xứ (`am_puck` + preset Praat `boy`). |
| **`speed`** | `float` | Không | `1.0` | **Tốc độ đọc (dải cho phép: `0.25` - `4.0`)**:<br>• Học từ vựng tiếng Anh mới: nên đặt `0.8` – `0.85` để học viên nghe rõ âm bật (ending sounds).<br>• Hướng dẫn hội thoại thông thường: đặt `1.0`. |
| **`response_format`** | `string` | Không | `"wav"` | Định dạng file âm thanh trả về: `"wav"`, `"mp3"`, `"opus"`, `"pcm"`, `"aac"`, `"flac"`.<br>*(Khuyến nghị dùng `"wav"` để đạt tốc độ nhanh nhất do sinh trực tiếp trên RAM).* |
| **`colon_pause_seconds`** | `float` | Không | `0.2` | Thời gian ngắt nghỉ vật lý (giây) khi gặp dấu hai chấm `:`. |
| **`ellipsis_pause_seconds`**| `float` | Không | `0.4` | Thời gian ngắt nghỉ vật lý (giây) khi gặp dấu ba chấm `...`. |
| **`model`** | `string` | Không | `"VietTTS"` | Tên mô hình khai báo (tương thích OpenAI, giá trị thực tế do `voice` quyết định). |

---

## 4. Kịch Bản Mẫu Cho Tính Năng Học Tiếng Anh (English Learning Flow)

Trong một bài học tương tác, client nên tách riêng phần hướng dẫn tiếng Việt và từ vựng tiếng Anh thành các request độc lập:

### Bước 1: Hướng dẫn bằng tiếng Việt
* **Voice**: `"vi_fe"`
* **Speed**: `1.0`
```json
{
  "voice": "vi_fe",
  "input": "Hôm nay chúng ta sẽ học từ vựng về chủ đề động vật. Hãy lắng nghe và nhắc lại theo cô nhé:",
  "speed": 1.0,
  "response_format": "wav"
}
```

### Bước 2: Phát âm từ vựng tiếng Anh mẫu (Đọc chậm, chuẩn âm)
* **Voice**: `"en_fe"`
* **Speed**: `0.85` *(giảm tốc độ nhẹ để phát âm từng âm vị rõ ràng)*
```json
{
  "voice": "en_fe",
  "input": "Butterfly.",
  "speed": 0.85,
  "response_format": "wav"
}
```

### Bước 3: Đọc câu ví dụ tiếng Anh (Tốc độ giao tiếp tự nhiên)
* **Voice**: `"en_fe"`
* **Speed**: `1.0`
```json
{
  "voice": "en_fe",
  "input": "The butterfly is flying in the garden.",
  "speed": 1.0,
  "response_format": "wav"
}
```

### Bước 4: Đánh giá và nhận xét học viên bằng tiếng Việt
* **Voice**: `"vi_fe"`
* **Speed**: `1.0`
```json
{
  "voice": "vi_fe",
  "input": "Rất tốt! Bạn phát âm từ này rất chuẩn.",
  "speed": 1.0,
  "response_format": "wav"
}
```

---

## 5. Code Mẫu Client Tích Hợp (Python)

### 5.1. Đồng bộ với thư viện `requests`

```python
import os
import requests

TTS_URL = os.getenv("TTS_URL", "http://localhost:13125/v1/audio/speech")
TTS_API_KEY = os.getenv("TTS_API_KEY", "ioit2025")

def text_to_speech(
    text: str,
    voice: str = "vi_fe",
    speed: float = 1.0,
    response_format: str = "wav"
) -> bytes:
    """
    Gửi yêu cầu tổng hợp tiếng nói sang TTS server.
    
    Args:
        text: Nội dung cần đọc.
        voice: 'vi_fe' | 'vi_ma' | 'en_fe' | 'en_ma'
        speed: Tốc độ đọc (0.8 - 0.85 cho từ vựng, 1.0 cho câu bình thường).
        response_format: Định dạng audio ('wav', 'mp3', 'opus', ...).
    Returns:
        Dữ liệu nhị phân (bytes) của file âm thanh.
    """
    headers = {
        "Authorization": f"Bearer {TTS_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "input": text.strip(),
        "voice": voice,
        "speed": speed,
        "response_format": response_format,
    }
    
    res = requests.post(TTS_URL, headers=headers, json=payload, timeout=30)
    if res.status_code != 200:
        raise RuntimeError(f"TTS Request Failed [{res.status_code}]: {res.text}")
        
    return res.content


# Ví dụ kịch bản bài học liên tục:
if __name__ == "__main__":
    # 1. Hướng dẫn tiếng Việt
    audio_intro = text_to_speech(
        text="Từ vựng tiếp theo là:",
        voice="vi_fe",
        speed=1.0
    )
    with open("01_intro.wav", "wb") as f:
        f.write(audio_intro)

    # 2. Phát âm từ vựng tiếng Anh (ngay sau đó, không cần chờ nạp lại model)
    audio_vocab = text_to_speech(
        text="Pronunciation.",
        voice="en_fe",
        speed=0.85
    )
    with open("02_vocab.wav", "wb") as f:
        f.write(audio_vocab)

    print("Hoàn tất tổng hợp chuỗi âm thanh học tiếng Anh!")
```

### 5.2. Bất đồng bộ với `httpx` (Khuyến nghị cho FastAPI / Bot async)

```python
import httpx

async def async_text_to_speech(
    client: httpx.AsyncClient,
    text: str,
    voice: str = "vi_fe",
    speed: float = 1.0,
    response_format: str = "wav"
) -> bytes:
    headers = {
        "Authorization": "Bearer ioit2025",
        "Content-Type": "application/json",
    }
    payload = {
        "input": text.strip(),
        "voice": voice,
        "speed": speed,
        "response_format": response_format,
    }
    resp = await client.post("http://localhost:13125/v1/audio/speech", headers=headers, json=payload, timeout=30.0)
    resp.raise_for_status()
    return resp.content
```

---

## 6. Các Thực Hành Tốt Nhất (Best Practices)

1. **Không trộn lẫn 2 thứ tiếng trong 1 câu**:
   * *Nên tránh*: Gửi `"Hãy đọc từ sau: Beautiful"` với `voice="vi_fe"` hoặc `voice="en_fe"`.
   * *Nên làm*: Gửi `"Hãy đọc từ sau:"` với `voice="vi_fe"`, sau đó gửi `"Beautiful"` với `voice="en_fe"`.
2. **Dấu kết thúc câu**:
   * Server có cơ chế tự động bù dấu chấm `.` nếu thiếu để ngăn lỗi hallucination, tuy nhiên tốt nhất client nên đảm bảo chuỗi text kết thúc rõ ràng bằng `.`, `!`, `?`.
3. **Định dạng file âm thanh**:
   * Nên dùng `"response_format": "wav"` vì server tạo trực tiếp trong RAM, giúp thời gian phản hồi (TTFB) đạt mức thấp nhất. Chỉ dùng `mp3` hoặc `opus` khi đường truyền mạng từ client đến server bị giới hạn băng thông.
