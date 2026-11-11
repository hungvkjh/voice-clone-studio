"""
Voice-Clone Studio — F5-TTS voice cloning server with a web UI.

Standalone fork of the horror/manhwa `tts-clone` server. It CLONES the timbre of
a chosen reference clip for every request and exposes:

    GET  /                 -> web UI (web/index.html)
    GET  /health           -> {"ok":true, "device":"cuda|cpu"}
    GET  /voices           -> [{"name","hasText","text"}]   list reference voices
    POST /voices?name=..   -> upload a new reference voice (raw audio body)
    POST /tts              -> synth, returns audio (mp3|wav) + X-Output-File header
    GET  /output/<file>    -> download a previously generated file
    GET  /outputs          -> recent generated files (history)

Tone controls (all applied after F5 synthesis):
    - speed     : F5 native speed (0.5 .. 1.5), slower < 1
    - pitch     : semitone shift (-12 .. +12) via ffmpeg asetrate/atempo (keeps tempo)
    - volume    : gain in dB (-20 .. +20)
    - normalize : EBU R128 loudness normalization (ffmpeg loudnorm)

Run (Windows), using the bundled uv env:
    .venv\\Scripts\\python.exe server.py
Then open http://127.0.0.1:8124
"""

import json
import os
import subprocess
import tempfile
import time
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))

HOST = os.environ.get("TTS_HOST", "127.0.0.1")
PORT = int(os.environ.get("TTS_PORT", "8124"))
MODEL = os.environ.get("F5_MODEL", "F5TTS_Base")
CKPT = os.environ.get("F5_CKPT", os.path.join(HERE, "models", "vivoice", "model_last.pt"))
VOCAB = os.environ.get("F5_VOCAB", os.path.join(HERE, "models", "vivoice", "vocab.txt"))
DEVICE = os.environ.get("F5_DEVICE", "auto")  # auto | cuda | cpu
DEFAULT_SPEED = float(os.environ.get("F5_SPEED", "0.9"))

VOICES_DIR = os.path.join(HERE, "voices")
OUTPUT_DIR = os.path.join(HERE, "output")
WEB_DIR = os.path.join(HERE, "web")
os.makedirs(VOICES_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

_f5 = None
_device = "cpu"
# cache of ref_text per voice name so we don't re-read the file every request
_ref_text_cache = {}


# --------------------------------------------------------------------------- #
# F5-TTS model
# --------------------------------------------------------------------------- #
def _pick_device() -> str:
    if DEVICE in ("cuda", "cpu"):
        return DEVICE
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def _new_f5(device: str):
    """Construct F5TTS across API versions (param renamed model_type->model)."""
    from f5_tts.api import F5TTS

    common = dict(ckpt_file=CKPT, vocab_file=VOCAB, device=device)
    try:
        return F5TTS(model=MODEL, **common)
    except TypeError:
        return F5TTS(model_type=MODEL, **common)


def _ensure_loaded():
    global _f5, _device
    if _f5 is not None:
        return
    _device = _pick_device()
    print(f"[studio] loading F5 model={MODEL} device={_device}")
    print(f"[studio]   ckpt={CKPT}")
    try:
        _f5 = _new_f5(_device)
    except Exception as e:
        if _device == "cuda":
            print(f"[studio] cuda load failed ({e}); falling back to CPU")
            _device = "cpu"
            _f5 = _new_f5("cpu")
        else:
            raise
    print("[studio] model ready")


# --------------------------------------------------------------------------- #
# Reference voices
# --------------------------------------------------------------------------- #
def _voice_wav(name: str) -> str:
    return os.path.join(VOICES_DIR, f"{name}.wav")


def _voice_txt(name: str) -> str:
    return os.path.join(VOICES_DIR, f"{name}.txt")


def _safe_name(name: str) -> str:
    keep = "-_. "
    cleaned = "".join(c for c in (name or "") if c.isalnum() or c in keep).strip()
    cleaned = cleaned.replace(" ", "-")
    return cleaned or "voice"


def list_voices():
    out = []
    for fn in sorted(os.listdir(VOICES_DIR)):
        if not fn.lower().endswith(".wav"):
            continue
        name = fn[:-4]
        txt_path = _voice_txt(name)
        text = ""
        if os.path.exists(txt_path):
            with open(txt_path, "r", encoding="utf-8") as f:
                text = f.read().strip()
        out.append({"name": name, "hasText": bool(text), "text": text})
    return out


def _ref_text_for(name: str) -> str:
    if name in _ref_text_cache:
        return _ref_text_cache[name]
    txt_path = _voice_txt(name)
    text = ""
    if os.path.exists(txt_path):
        with open(txt_path, "r", encoding="utf-8") as f:
            text = f.read().strip()
    # Empty ref_text makes F5 auto-transcribe the reference (slower, needs ASR).
    _ref_text_cache[name] = text
    return text


def _try_transcribe(wav_path: str) -> str:
    """Best-effort Vietnamese transcription of an uploaded reference clip."""
    try:
        from faster_whisper import WhisperModel

        m = WhisperModel("medium", device="cpu", compute_type="int8")
        segs, _ = m.transcribe(wav_path, language="vi", beam_size=5)
        return " ".join(s.text.strip() for s in segs).strip()
    except Exception as e:
        print(f"[studio] auto-transcribe skipped: {e}")
        return ""


def save_voice(name: str, raw: bytes, text: str) -> dict:
    """Store an uploaded clip as a reference voice (mono 24k wav + transcript)."""
    name = _safe_name(name)
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "in")
        with open(src, "wb") as f:
            f.write(raw)
        wav_path = _voice_wav(name)
        # Normalize any input (mp3/wav/m4a) to clean mono 24kHz for F5.
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
             "-i", src, "-ac", "1", "-ar", "24000", wav_path],
            capture_output=True,
        )
        if r.returncode != 0:
            raise RuntimeError(f"ffmpeg convert failed: {r.stderr.decode('utf-8','replace')[:300]}")
    text = (text or "").strip()
    if not text:
        text = _try_transcribe(wav_path)
    if text:
        with open(_voice_txt(name), "w", encoding="utf-8") as f:
            f.write(text)
    _ref_text_cache.pop(name, None)
    return {"name": name, "hasText": bool(text), "text": text}


# --------------------------------------------------------------------------- #
# Synthesis + tone post-processing
# --------------------------------------------------------------------------- #
def _rate_to_speed(rate) -> float:
    """edge-tts style '-12%'/'+8%' or a bare float -> F5 speed multiplier."""
    if rate is None or rate == "":
        return DEFAULT_SPEED
    s = str(rate).strip().replace("%", "")
    try:
        val = float(s)
    except ValueError:
        return DEFAULT_SPEED
    # Percent form ('-12%') arrives as -12 -> 0.88; a plain speed ('0.9') stays.
    if abs(val) > 2.0:
        val = 1.0 + val / 100.0
    return max(0.5, min(1.5, val))


def _post_filters(pitch: float, volume: float, normalize: bool):
    """Build an ffmpeg -af chain for pitch/volume/loudness. Empty if no-op."""
    filters = []
    if pitch and abs(pitch) > 0.01:
        factor = 2 ** (pitch / 12.0)          # semitone -> frequency ratio
        sr = 24000
        filters.append(f"asetrate={int(sr * factor)}")
        filters.append(f"aresample={sr}")
        # restore original tempo (atempo accepts 0.5..2.0; split if needed)
        inv = 1.0 / factor
        while inv < 0.5:
            filters.append("atempo=0.5")
            inv /= 0.5
        while inv > 2.0:
            filters.append("atempo=2.0")
            inv /= 2.0
        filters.append(f"atempo={inv:.6f}")
    if volume and abs(volume) > 0.01:
        filters.append(f"volume={volume}dB")
    if normalize:
        filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
    return filters


def _encode(wav_path: str, fmt: str, filters) -> bytes:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", wav_path]
    if filters:
        cmd += ["-af", ",".join(filters)]
    if fmt == "wav":
        cmd += ["-c:a", "pcm_s16le", "-f", "wav", "pipe:1"]
    else:
        cmd += ["-c:a", "libmp3lame", "-q:a", "2", "-f", "mp3", "pipe:1"]
    out = subprocess.run(cmd, capture_output=True)
    if out.returncode != 0 or not out.stdout:
        raise RuntimeError(f"ffmpeg encode failed: {out.stderr.decode('utf-8','replace')[:300]}")
    return out.stdout


def synth(text: str, voice: str, speed: float, pitch: float,
          volume: float, normalize: bool, fmt: str) -> bytes:
    global _f5, _device
    _ensure_loaded()
    ref_audio = _voice_wav(voice)
    if not os.path.exists(ref_audio):
        raise RuntimeError(f"unknown voice '{voice}'")
    ref_text = _ref_text_for(voice)
    with tempfile.TemporaryDirectory() as td:
        wav_path = os.path.join(td, "out.wav")
        last = None
        for _ in range(2):
            try:
                _f5.infer(
                    ref_file=ref_audio,
                    ref_text=ref_text,
                    gen_text=text,
                    speed=speed,
                    remove_silence=True,
                    file_wave=wav_path,
                )
                break
            except RuntimeError as e:
                last = e
                msg = str(e).lower()
                if "out of memory" in msg or "cuda" in msg:
                    print(f"[studio] infer error ({e}); rebuilding on CPU")
                    try:
                        import torch

                        torch.cuda.empty_cache()
                    except Exception:
                        pass
                    _device = "cpu"
                    _f5 = _new_f5("cpu")
                    continue
                raise
        else:
            raise last if last else RuntimeError("F5 infer failed")
        return _encode(wav_path, fmt, _post_filters(pitch, volume, normalize))


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def _f(payload, key, default):
    try:
        v = payload.get(key)
        return default if v is None or v == "" else float(v)
    except (TypeError, ValueError):
        return default


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype, extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False), "application/json; charset=utf-8")

    # -- GET -------------------------------------------------------------- #
    def do_GET(self):  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._serve_file(os.path.join(WEB_DIR, "index.html"), "text/html; charset=utf-8")
        elif path == "/health":
            self._json(200, {"ok": True, "device": _device})
        elif path == "/voices":
            self._json(200, list_voices())
        elif path == "/outputs":
            self._json(200, self._list_outputs())
        elif path.startswith("/output/"):
            self._serve_output(os.path.basename(path))
        elif path.startswith("/web/"):
            self._serve_file(os.path.join(WEB_DIR, os.path.basename(path)), self._ctype(path))
        else:
            self._send(404, "not found", "text/plain")

    def _ctype(self, path):
        if path.endswith(".css"):
            return "text/css; charset=utf-8"
        if path.endswith(".js"):
            return "application/javascript; charset=utf-8"
        return "application/octet-stream"

    def _serve_file(self, fpath, ctype):
        if not os.path.exists(fpath):
            self._send(404, "not found", "text/plain")
            return
        with open(fpath, "rb") as f:
            self._send(200, f.read(), ctype)

    def _list_outputs(self):
        items = []
        for fn in os.listdir(OUTPUT_DIR):
            if not fn.lower().endswith((".mp3", ".wav")):
                continue
            fp = os.path.join(OUTPUT_DIR, fn)
            if os.path.isfile(fp):
                items.append({"file": fn, "mtime": os.path.getmtime(fp), "size": os.path.getsize(fp)})
        items.sort(key=lambda x: x["mtime"], reverse=True)
        return items[:50]

    def _serve_output(self, fn):
        fp = os.path.join(OUTPUT_DIR, os.path.basename(fn))
        if not os.path.isfile(fp):
            self._send(404, "not found", "text/plain")
            return
        ctype = "audio/wav" if fn.endswith(".wav") else "audio/mpeg"
        with open(fp, "rb") as f:
            self._send(200, f.read(), ctype,
                       {"Content-Disposition": f'attachment; filename="{fn}"'})

    # -- POST ------------------------------------------------------------- #
    def do_POST(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b""
        if path == "/tts":
            self._handle_tts(body)
        elif path == "/voices":
            self._handle_upload(parsed, body)
        else:
            self._json(404, {"error": "unknown endpoint"})

    def _handle_tts(self, body):
        try:
            payload = json.loads(body or b"{}")
            text = (payload.get("text") or "").strip()
            if not text:
                self._json(400, {"error": "missing text"})
                return
            voice = _safe_name(payload.get("voice") or "horror")
            speed = _rate_to_speed(payload.get("rate", payload.get("speed")))
            pitch = max(-12.0, min(12.0, _f(payload, "pitch", 0.0)))
            volume = max(-20.0, min(20.0, _f(payload, "volume", 0.0)))
            normalize = bool(payload.get("normalize", False))
            fmt = "wav" if (payload.get("format") == "wav") else "mp3"

            audio = synth(text, voice, speed, pitch, volume, normalize, fmt)

            stamp = time.strftime("%Y%m%d-%H%M%S")
            fn = f"{voice}_{stamp}_{uuid.uuid4().hex[:6]}.{fmt}"
            with open(os.path.join(OUTPUT_DIR, fn), "wb") as f:
                f.write(audio)
            ctype = "audio/wav" if fmt == "wav" else "audio/mpeg"
            self._send(200, audio, ctype, {
                "X-Output-File": fn,
                "Content-Disposition": f'inline; filename="{fn}"',
                "Access-Control-Expose-Headers": "X-Output-File",
            })
        except Exception as e:  # noqa: BLE001
            self._json(500, {"error": str(e)})

    def _handle_upload(self, parsed, body):
        try:
            q = urllib.parse.parse_qs(parsed.query)
            name = (q.get("name", [""])[0]).strip()
            text = (q.get("text", [""])[0]).strip()
            if not name:
                self._json(400, {"error": "missing ?name="})
                return
            if not body:
                self._json(400, {"error": "empty audio body"})
                return
            info = save_voice(name, body, text)
            self._json(200, info)
        except Exception as e:  # noqa: BLE001
            self._json(500, {"error": str(e)})

    def log_message(self, fmt, *args):
        print(f"[studio] {self.address_string()} {fmt % args}")


def main():
    _ensure_loaded()  # warm up so the first request isn't slow / doesn't race
    print(f"[studio] listening on http://{HOST}:{PORT}   device={_device}")
    print(f"[studio] open the web UI at http://{HOST}:{PORT}/")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
