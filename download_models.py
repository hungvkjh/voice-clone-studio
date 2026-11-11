"""
Tải model F5-TTS tiếng Việt (ViVoice) về models/vivoice/.

Chỉ tải file nặng `model_last.pt` (~5GB) từ HuggingFace. File `vocab.txt` (11KB)
đã nằm sẵn trong repo. Hỗ trợ resume (chạy lại nếu bị ngắt giữa chừng).

Dùng:
    .venv\\Scripts\\python.exe download_models.py
"""

import os
import sys

try:  # dam bao in duoc tieng Viet du console dung cp1252
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(HERE, "models", "vivoice")

REPO_ID = os.environ.get("F5_REPO", "hynt/F5-TTS-Vietnamese-ViVoice")
WEIGHTS = "model_last.pt"
VOCAB = "vocab.txt"


def main():
    os.makedirs(DEST, exist_ok=True)

    vocab_path = os.path.join(DEST, VOCAB)
    if not os.path.exists(vocab_path):
        print(f"[!] Thiếu {vocab_path} — file này đi kèm repo, hãy clone lại đầy đủ.")
    else:
        print(f"[ok] vocab.txt đã có ({os.path.getsize(vocab_path)} bytes)")

    weights_path = os.path.join(DEST, WEIGHTS)
    if os.path.exists(weights_path) and os.path.getsize(weights_path) > 1_000_000_000:
        print(f"[ok] {WEIGHTS} đã có ({os.path.getsize(weights_path)/1e9:.2f} GB) — bỏ qua tải.")
        return

    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("[x] Chưa cài huggingface_hub. Chạy install.bat trước.")
        sys.exit(1)

    print(f"[..] Đang tải {REPO_ID}/{WEIGHTS} (~5GB) về {DEST} ...")
    print("     (có resume — nếu ngắt cứ chạy lại script này)")
    path = hf_hub_download(
        repo_id=REPO_ID,
        filename=WEIGHTS,
        local_dir=DEST,
    )
    size = os.path.getsize(path) / 1e9
    print(f"[ok] Xong: {path} ({size:.2f} GB)")


if __name__ == "__main__":
    main()
