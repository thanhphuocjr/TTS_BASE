# HƯỚNG DẪN TRIỂN KHAI STREAMINGTTS LÊN SERVER MỚI (DEPLOYMENT GUIDE)

Tài liệu này hướng dẫn chi tiết từng bước để cài đặt và triển khai hệ thống **StreamingTTS** từ đầu lên một **máy chủ GPU hoàn toàn mới (New Server)** bằng phương pháp đóng gói Docker Image.

---

## 📌 TỔNG QUAN QUY TRÌNH

```text
┌────────────────────────┐                    ┌────────────────────────┐
│   SERVER CŨ (Hiện tại) │                    │    MÁY CHỦ MỚI TINH    │
│  Image: streamingtts:v7│                    │ (Ubuntu + NVIDIA GPU)  │
└───────────┬────────────┘                    └───────────▲────────────┘
            │ docker save                                 │
            ▼                                             │ docker load
  streamingtts_v7.tar.gz  ──────[ scp / copy ]────────────┤
                                                          │
┌────────────────────────┐                                │
│       MÁY LOCAL        │───────[ rsync ]────────────────┘
│   (Mã nguồn + voices)  │ (app, config, voices, Dockerfile...)
└────────────────────────┘
```

---

## PHẦN 1: YÊU CẦU & CHUẨN BỊ MÔI TRƯỜNG TRÊN SERVER MỚI

### 1.1. Yêu cầu phần cứng & hệ điều hành
- **Hệ điều hành:** Linux (Khuyên dùng Ubuntu 22.04 LTS hoặc 20.04 LTS).
- **GPU:** NVIDIA GPU với tối thiểu **8GB - 16GB VRAM** (RTX 3090, RTX 4090, A100, L4, T4...).
- **Ổ cứng:** Tối thiểu **60GB trống** (chứa Docker image, cache weights và log âm thanh).
- **Driver:** NVIDIA Driver tương thích với CUDA $\ge 12.0$.

Kiểm tra driver GPU trên server mới:
```bash
nvidia-smi
```
*(Nếu hiện bảng thông tin GPU là driver đã sẵn sàng. Nếu chưa có, cần cài driver NVIDIA trước).*

---

### 1.2. Cài đặt Docker Engine & NVIDIA Container Toolkit
> [!IMPORTANT]
> Bắt buộc phải cài **NVIDIA Container Toolkit** thì Docker mới có thể sử dụng GPU qua cờ `--gpus all`.

Chạy các lệnh sau trên Server Mới:

```bash
# 1. Cài Docker Engine
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 2. Thêm repository cho NVIDIA Container Toolkit
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
  && curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# 3. Cài đặt toolkit và cấu hình runtime Docker
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker

# 4. Khởi động lại dịch vụ Docker
sudo systemctl restart docker

# 5. Kiểm tra Docker đã nhận GPU chưa
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

---

## PHẦN 2: LẤY IMAGE VÀ CODE TỪ SERVER HIỆN TẠI CHUYỂN SANG SERVER MỚI

Bạn có thể chuyển trực tiếp từ **Server Cũ sang Server Mới** (hoặc chuyển từ máy Mac) theo 2 bước:

### 2.1. Tại Server Cũ: Đóng gói Docker Image
Image `streamingtts:v7` đã chứa sẵn toàn bộ môi trường CUDA và weights mô hình (~30GB). Đóng gói thành file nén:

```bash
# SSH vào Server Cũ:
docker save streamingtts:v7 | gzip > ~/Desktop/streamingtts_v7.tar.gz
```
*(Quá trình nén mất khoảng 3 - 5 phút tùy tốc độ đĩa).*

---

### 2.2. Tại Server Cũ: Đóng gói thư mục Code & Voices
Trên Server Cũ, nén toàn bộ thư mục code `streamingtts-v7`:

```bash
# SSH vào Server Cũ:
tar -czvf ~/Desktop/streamingtts_v7_code.tar.gz \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.DS_Store' \
  -C ~/Desktop streamingtts-v7
```

---

### 2.3. Chuyển Image và Code từ Server Cũ sang Server Mới
Chuyển cả 2 file nén sang Server Mới qua lệnh `scp`:

```bash
# Chạy trên Server Cũ:
scp -P [PORT_SERVER_MOI] ~/Desktop/streamingtts_v7.tar.gz user@IP_SERVER_MOI:~/Desktop/
scp -P [PORT_SERVER_MOI] ~/Desktop/streamingtts_v7_code.tar.gz user@IP_SERVER_MOI:~/Desktop/
```

*(Hoặc dùng rsync trực tiếp từ Server Cũ sang Server Mới):*
```bash
rsync -avz --delete \
  --exclude '__pycache__/' --exclude '*.pyc' \
  -e "ssh -p [PORT_SERVER_MOI]" \
  ~/Desktop/streamingtts-v7/ \
  user@IP_SERVER_MOI:~/Desktop/streamingtts-v7/
```

*(Tùy chọn phụ): Nếu bạn muốn đẩy code từ máy Mac thay vì từ Server Cũ:*
```bash
# Chạy từ máy Mac:
rsync -avz --delete \
  --exclude '__pycache__/' --exclude '*.pyc' --exclude '.DS_Store' \
  -e "ssh -p [PORT_SERVER_MOI]" \
  app config engines text_normalizer presets voices requirements.txt Dockerfile \
  user@IP_SERVER_MOI:~/Desktop/streamingtts-v7/
```

---

## PHẦN 3: NẠP IMAGE, BUILD VÀ KHỞI CHẠY TRÊN SERVER MỚI

SSH vào **Server Mới** (`ssh -p [PORT_SERVER_MOI] user@IP_SERVER_MOI`):

### 3.1. Giải nén mã nguồn
```bash
cd ~/Desktop
tar -xzvf streamingtts_v7_code.tar.gz
cd ~/Desktop/streamingtts-v7
```

---

### 3.2. Nạp Docker Image vào hệ thống
```bash
docker load < ~/Desktop/streamingtts_v7.tar.gz
```
*(Sau khi nạp xong, gõ `docker images` bạn sẽ thấy `streamingtts:v7` xuất hiện).*

---

### 3.3. Đặt tag Base Image để phục vụ việc Build lại
```bash
# Tag bản v7 thành v5 để lệnh build (FROM streamingtts:v5) trong Dockerfile hoạt động
docker tag streamingtts:v7 streamingtts:v5
```

---

### 3.4. Build lại Docker Image trên Server Mới
Đảm bảo image được build hoàn chỉnh khớp với code tại Server Mới:

```bash
cd ~/Desktop/streamingtts-v7

# Build image streamingtts:v7 từ code vừa giải nén
docker build -t streamingtts:v7 .
```

---

### 3.5. Tạo thư mục lưu logs và Khởi chạy Container
```bash
# 1. Tạo thư mục lưu trữ logs
mkdir -p ~/Desktop/TTS_13127/logs

# 2. Xoá container cũ nếu có
docker rm -f streamingtts-v7 2>/dev/null || true

# 3. Khởi chạy container mới ở cổng 13127
docker run -d \
  --name streamingtts-v7 \
  --restart unless-stopped \
  --gpus all \
  -p 13127:13127 \
  -v ~/Desktop/TTS_13127/logs:/app/logs \
  -v ~/Desktop/streamingtts-v7/voices:/app/voices \
  streamingtts:v7
```

> [!TIP]
> Nếu máy chủ mới có nhiều GPU và bạn muốn chỉ định chạy trên một GPU cụ thể (ví dụ GPU 0 hoặc GPU 1), thêm cờ môi trường `-e TTS_VIETTTS_DEVICE=cuda:0` hoặc dùng `--gpus '"device=0"'`.

---

## PHẦN 4: KIỂM TRA HOẠT ĐỘNG & TEST ÂM THANH

### 4.1. Kiểm tra log khởi động trên Server
```bash
docker logs -f streamingtts-v7
```
Khi màn hình hiển thị:
```text
INFO: [tts_server] All models ready
INFO: Uvicorn running on http://0.0.0.0:13127 (Press CTRL+C to quit)
```
Nghĩa là toàn bộ model VietTTS và EngTTS đã nạp vào VRAM thành công!

---

### 4.2. Kiểm tra Health Check
```bash
curl http://127.0.0.1:13127/health
```
Kết quả trả về JSON hợp lệ:
```json
{"status":"ok","models":["VietTTS","EngTTS"],"voices":["vi_fe","vi_ma","en_fe","en_ma"]}
```

---

### 4.3. Test tạo âm thanh từ máy Mac
Từ máy Mac, chạy script test trỏ tới IP server mới:

```bash
BASE_URL=http://IP_SERVER_MOI:13127 ./test_13127.sh
```
File âm thanh `.wav` sẽ được tải về máy Mac và tự động phát âm thanh kiểm tra.

---

## PHẦN 5: XỬ LÝ SỰ CỐ THƯỜNG GẶP (TROUBLESHOOTING)

### 1. Lỗi: `could not select device driver "" with capabilities: [[gpu]]`
- **Nguyên nhân:** Docker chưa nhận diện runtime NVIDIA.
- **Khắc phục:** Chạy lại:
  ```bash
  sudo nvidia-ctk runtime configure --runtime=docker
  sudo systemctl restart docker
  ```

### 2. Lỗi: `address already in use` khi chạy container
- **Nguyên nhân:** Cổng `13127` đang bị chiếm bởi tiến trình khác.
- **Khắc phục:** 
  Kiểm tra tiến trình đang chiếm cổng:
  ```bash
  sudo lsof -i :13127
  # Hoặc đổi cổng host ngoài lệnh docker run, ví dụ: -p 13128:13127
  ```

### 3. Cập nhật code mới sau này trên server mới
Khi bạn sửa code ở máy Mac và muốn cập nhật lên server mới:
```bash
# 1. Tại Mac: rsync code lên server mới
rsync -avz --delete \
  --exclude '__pycache__/' --exclude '*.pyc' --exclude '.DS_Store' \
  -e "ssh -p [PORT]" \
  app config engines text_normalizer presets voices requirements.txt Dockerfile \
  user@IP_SERVER_MOI:~/Desktop/streamingtts-v7/

# 2. Tại Server Mới: build và chạy lại
cd ~/Desktop/streamingtts-v7/
docker build -t streamingtts:v7 .
docker rm -f streamingtts-v7
docker run -d \
  --name streamingtts-v7 \
  --restart unless-stopped \
  --gpus all \
  -p 13127:13127 \
  -v ~/Desktop/TTS_13127/logs:/app/logs \
  -v ~/Desktop/streamingtts-v7/voices:/app/voices \
  streamingtts:v7
```
