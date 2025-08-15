import os
import threading
from typing import Generator, Dict, Optional, List, Tuple

try:
    import torch  # for device auto-detection
except Exception:
    torch = None  # type: ignore

from faster_whisper import WhisperModel

_model: Optional[WhisperModel] = None
_lock = threading.Lock()


def _get_env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}


def _select_device(explicit: str) -> str:
    if explicit and explicit.lower() in {"cpu", "cuda"}:
        return explicit.lower()
    if explicit and explicit.lower() == "auto":
        pass
    # auto
    if torch is not None and hasattr(torch, "cuda") and torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _compute_type_for_device(device: str) -> str:
    env_val = os.getenv("FW_COMPUTE")
    if env_val:
        return env_val
    return "int8_float16" if device == "cuda" else "int8"


def _load_model() -> WhisperModel:
    global _model
    with _lock:
        if _model is None:
            # Use configurable model size with tiny as default
            model_name = os.getenv("FW_MODEL", "tiny")
            device = _select_device(os.getenv("FW_DEVICE", "auto"))
            compute_type = _compute_type_for_device(device)
            num_workers = int(os.getenv("FW_WORKERS", "2"))
            cpu_threads = max(1, (os.cpu_count() or 2) // 2)

            _model = WhisperModel(
                model_name,
                device=device,
                compute_type=compute_type,
                cpu_threads=cpu_threads,
                num_workers=num_workers,
            )
        return _model


def transcribe_audio_stream(
    input_wav_path: str,
    lang_hint: Optional[str] = None,
) -> Generator[Dict[str, object], None, None]:
    model = _load_model()

    vad_filter = _get_env_bool("FW_VAD", True)
    beam_size = int(os.getenv("FW_BEAM", "1"))
    temperature_env = os.getenv("FW_TEMP", "0")
    try:
        temperature = float(temperature_env)
    except Exception:
        temperature = 0.0
    chunk_len = int(os.getenv("FW_CHUNK", "60"))

    segments, _info = model.transcribe(
        input_wav_path,
        language=(lang_hint or None),
        beam_size=beam_size,
        temperature=temperature,
        vad_filter=vad_filter,
        chunk_length=chunk_len,
        condition_on_previous_text=False,
    )

    for seg in segments:
        yield {
            "text": seg.text,
            "start": seg.start,
            "end": seg.end,
        }


def transcribe_and_collect(
    input_wav_path: str,
    lang_hint: Optional[str] = None,
) -> Tuple[str, List[Dict[str, object]]]:
    transcript_parts: List[str] = []
    timeline: List[Dict[str, object]] = []
    for chunk in transcribe_audio_stream(input_wav_path, lang_hint):
        timeline.append(chunk)
        text = str(chunk.get("text", "")).strip()
        if text:
            transcript_parts.append(text)
    return (" ".join(transcript_parts).strip(), timeline)


