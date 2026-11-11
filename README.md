# Voice-Clone Studio 🎙️

Công cụ **nhân bản chất giọng** (voice cloning) độc lập, có **web UI**. Nhập văn
bản tiếng Việt → clone giọng từ clip mẫu → nghe và tải file về, có nút chỉnh
**tốc độ / cao độ / âm lượng / chuẩn hoá**.

Tách ra từ pipeline `AI-auto-generate-video` (phần `tts-clone`) để dùng riêng cho
việc clone giọng. Chạy hoàn toàn độc lập — đã kèm sẵn Python env và model.

![engine](https://img.shields.io/badge/engine-F5--TTS%20(ViVoice)-7c5cff) ![ui](https://img.shields.io/badge/web%20UI-included-00d4a0)

---

## Cài đặt (máy mới / cho người khác dùng)

Repo không kèm sẵn môi trường Python và model nặng. Trên máy mới chỉ cần:

```bat
install.bat
```

Script sẽ tự: tạo venv **Python 3.11** → cài **torch + f5-tts** → **tải model ~5GB**.

**Yêu cầu:**
- Windows, có **ffmpeg** trong PATH — cài: `winget install Gyan.FFmpeg`
- Một trong hai: **[uv](https://docs.astral.sh/uv/)** (khuyên dùng, tự tải Python 3.11) *hoặc* **Python 3.11** cài sẵn.
- Máy có **GPU NVIDIA** → để mặc định (`cu124`). **Không có GPU** → chạy:
  ```bat
  set TORCH_VARIANT=cpu
  install.bat
  ```
  (CPU chạy được nhưng chậm hơn nhiều.)

Cài xong → `start.bat`. Nếu chỉ muốn tải lại model: `.venv\Scripts\python.exe download_models.py`.

> Model tải từ HuggingFace `hynt/F5-TTS-Vietnamese-ViVoice` (`model_last.pt`). File `vocab.txt` đã nằm sẵn trong repo.

---

## Chạy nhanh

```bat
start.bat
```

Lần đầu tải vocoder Vocos (~50MB). Khi thấy `listening on http://127.0.0.1:8124`
trình duyệt sẽ tự mở web UI. Nếu không, mở tay: <http://127.0.0.1:8124/>

> Cần **ffmpeg** trong PATH (để chỉnh pitch/volume/normalize và xuất mp3/wav).

### Dùng web UI
1. Dán văn bản cần đọc.
2. Chọn **giọng mẫu** (mặc định: `horror`, `nam-tram`).
3. Kéo các thanh **Tốc độ / Cao độ / Âm lượng**, tick **Chuẩn hoá** nếu muốn, chọn **MP3/WAV**.
4. Bấm **Tạo giọng** → nghe ngay, bấm **Tải file về**.
5. Muốn giọng khác: mở **➕ Thêm giọng mẫu mới**, upload clip 6–12s + (tuỳ chọn) lời thoại.

---

## API (dùng cho pipeline khác)

Cùng contract với server edge-tts cũ nên là bản thay thế thả-vào:

```
GET  /health            -> {"ok":true,"device":"cuda|cpu"}
GET  /voices            -> [{"name","hasText","text"}]
POST /voices?name=X     -> upload clip (body = raw audio) làm giọng mẫu mới
POST /tts               -> trả audio (mp3/wav), header X-Output-File
GET  /output/<file>     -> tải lại file đã tạo
```

Body `POST /tts`:

```json
{
  "text": "Xin chào...",
  "voice": "horror",
  "speed": 0.9,          // 0.5..1.5 (hoặc "rate":"-12%")
  "pitch": 0,            // -12..+12 nửa cung
  "volume": 0,           // -20..+20 dB
  "normalize": false,    // loudnorm EBU R128
  "format": "mp3"        // "mp3" | "wav"
}
```

Ví dụ:

```bash
curl -X POST http://127.0.0.1:8124/tts \
  -H "Content-Type: application/json" \
  -d '{"text":"Căn nhà cuối ngõ đã bỏ hoang.","voice":"horror","speed":0.85,"pitch":-2}' \
  --output out.mp3
```

---

## Điều chỉnh giọng điệu — cơ chế

| Nút | Cách hoạt động |
|---|---|
| **Tốc độ** | `speed` native của F5-TTS (nhịp đọc). |
| **Cao độ** | ffmpeg `asetrate`+`atempo` (dịch nửa cung, **giữ nguyên nhịp**). |
| **Âm lượng** | ffmpeg `volume=XdB`. |
| **Chuẩn hoá** | ffmpeg `loudnorm` (EBU R128, I=-16). |

Giọng (timbre) do **clip mẫu** quyết định — đổi giọng = đổi `voice`/upload clip mới.

---

## Thành phần

| Thứ | Đường dẫn |
|---|---|
| Server + web UI | `server.py`, `web/index.html` |
| Cài đặt + tải model | `install.bat`, `download_models.py`, `requirements.txt` |
| Môi trường Python 3.11 | `.venv/` *(install.bat tạo, ~5.5GB)* |
| Model | `models/vivoice/model_last.pt` *(~5GB, download_models.py tải)* |
| Vocab | `models/vivoice/vocab.txt` *(kèm repo, 11KB)* |
| Giọng mẫu | `voices/<name>.wav` (+ `<name>.txt` lời thoại) |
| File đã tạo | `output/` |

## Biến môi trường (tuỳ chọn)

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `TTS_PORT` | `8124` | Cổng server |
| `F5_DEVICE` | `cuda` | `cuda` \| `cpu` \| `auto` |
| `F5_SPEED` | `0.9` | Tốc độ mặc định khi request không truyền |
| `F5_CKPT` | `models/vivoice/model_last.pt` | Đường dẫn checkpoint |
| `F5_REPO` | `hynt/F5-TTS-Vietnamese-ViVoice` | Repo HF để `download_models.py` tải |
| `TORCH_VARIANT` | `cu124` | `cu124` (GPU) \| `cpu` — dùng khi chạy `install.bat` |

## Thêm giọng mẫu (không qua web)

Bỏ file vào `voices/`:
- `voices/<tên>.wav` — clip sạch, 6–12s, một giọng.
- `voices/<tên>.txt` — lời thoại trong clip (giúp clone chuẩn hơn; để trống thì F5 tự nhận dạng, chậm hơn).
