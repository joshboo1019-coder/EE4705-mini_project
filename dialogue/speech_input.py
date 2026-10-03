"""
speech_input.py — STUDENT B OWNS THIS FILE. Bonus: spoken commands.

Push-to-talk for the Task 3 chat loop: typing "v" + Enter records up to
MAX_RECORD_S of microphone audio (stopping early after SILENCE_STOP_S of
silence), transcribes it locally with faster-whisper (no API key; also
detects the language), prints

    [STT] text="<transcript>" lang=<code> p=<lang prob> t=<latency> s

and then hands the transcript to chat_interface.handle_utterance(), so
everything after that is identical to typed input. Speech confidently
detected as non-English is rejected here, before any LLM call.

Audio comes from `arecord` (ALSA/PipeWire default source), so no
PortAudio is needed.
"""

import subprocess
import time
from typing import Callable, Dict, Iterable, List, Optional, Tuple

import numpy as np

from core.schema import CommandQueue
from dialogue import llm_parser

VOICE_TRIGGER = "v"            # typed alone in the chat loop
SAMPLE_RATE = 16000
FRAME_S = 0.03
MAX_RECORD_S = 5.0
SILENCE_STOP_S = 1.0           # stop this long after speech has ended
SKIP_START_S = 0.5             # the device "pops" for ~0.5 s when opened
SPEECH_DBFS = -32.0            # frame counts as speech above this (room noise is ~-41 dBFS)
NON_EN_MIN_PROB = 0.5          # reject only if non-English with at least this confidence
WHISPER_MODEL = "small"        # multilingual
# Biases decoding towards the command words (eval/stt_eval.md, "initial_prompt").
# Language ID runs before decoding and does not see it.
WHISPER_PROMPT = ("walk, turn, left, right, forward, back, sidestep, shuffle, seconds, degrees, "
                  "chair, ball, stop sign, green, red, orange")

Transcript = Tuple[str, str, float]   # text, language code, language probability


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------

def _arecord_frames() -> Iterable[np.ndarray]:
    """int16 mono frames of FRAME_S from the default capture device."""
    n = int(SAMPLE_RATE * FRAME_S)
    proc = subprocess.Popen(
        ["arecord", "-q", "-t", "raw", "-f", "S16_LE", "-r", str(SAMPLE_RATE), "-c", "1"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        while True:
            buf = proc.stdout.read(2 * n)
            if len(buf) < 2 * n:
                return
            yield np.frombuffer(buf, dtype=np.int16)
    finally:
        proc.terminate()
        proc.wait(timeout=2)


def _dbfs(frame: np.ndarray) -> float:
    rms = float(np.sqrt(np.mean(frame.astype(np.float64) ** 2)))
    return 20.0 * np.log10(max(rms, 1.0) / 32768.0)


def record(frames: Optional[Iterable[np.ndarray]] = None) -> np.ndarray:
    """Push-to-talk capture. Returns float32 audio in [-1, 1] at SAMPLE_RATE,
    or an empty array if no frame rose above SPEECH_DBFS."""
    frames = _arecord_frames() if frames is None else frames
    print(f"[MIC] listening (up to {MAX_RECORD_S:.0f} s, stops after "
          f"{SILENCE_STOP_S:.0f} s of silence)...", flush=True)
    kept: List[np.ndarray] = []
    t = 0.0
    heard = False
    quiet = 0.0
    for frame in frames:
        t += FRAME_S
        if t <= SKIP_START_S:
            continue
        kept.append(frame)
        if _dbfs(frame) > SPEECH_DBFS:
            heard, quiet = True, 0.0
        else:
            quiet += FRAME_S
        if (heard and quiet >= SILENCE_STOP_S) or t >= SKIP_START_S + MAX_RECORD_S:
            break
    if hasattr(frames, "close"):
        frames.close()      # stops arecord
    audio = np.concatenate(kept) if kept else np.zeros(0, np.int16)
    print(f"[MIC] captured {len(audio) / SAMPLE_RATE:.1f} s"
          f"{'' if heard else ' (no speech)'}", flush=True)
    if not heard:
        return np.zeros(0, np.float32)
    return audio.astype(np.float32) / 32768.0


# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------

class WhisperTranscriber:
    """faster-whisper, loaded on first use: CUDA float16 if available,
    else CPU int8."""

    def __init__(self, model_size: str = WHISPER_MODEL):
        self.model_size = model_size
        self._model = None
        self.device = None

    def _load(self):
        from faster_whisper import WhisperModel
        t0 = time.time()
        try:
            self._model = WhisperModel(self.model_size, device="cuda", compute_type="float16")
            self.device = "cuda"
        except Exception:
            self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
            self.device = "cpu"
        print(f"[STT] loaded faster-whisper {self.model_size} on {self.device} "
              f"in {time.time() - t0:.1f} s", flush=True)

    def transcribe(self, audio: np.ndarray) -> Transcript:
        if self._model is None:
            self._load()
        segments, info = self._model.transcribe(
            audio, beam_size=5, vad_filter=True, condition_on_previous_text=False,
            initial_prompt=WHISPER_PROMPT)
        text = " ".join(s.text.strip() for s in segments).strip()
        return text, info.language, float(info.language_probability)


_transcriber: Optional[WhisperTranscriber] = None


def get_transcriber() -> WhisperTranscriber:
    global _transcriber
    if _transcriber is None:
        _transcriber = WhisperTranscriber()
    return _transcriber


# ---------------------------------------------------------------------------
# Push-to-talk turn
# ---------------------------------------------------------------------------

def handle_voice(history: List[Dict[str, str]], queue: CommandQueue,
                 record_fn: Callable[[], np.ndarray] = record,
                 transcriber=None) -> llm_parser.ParseResult:
    """One spoken turn: record -> transcribe -> (reject | handle_utterance)."""
    from dialogue import chat_interface   # imported here: chat_interface imports us lazily

    audio = record_fn()
    if audio.size == 0:
        print('[STT] text="" lang=- p=0.00 t=0.00 s', flush=True)
        return llm_parser._reject("empty")

    transcriber = transcriber or get_transcriber()
    t0 = time.time()
    text, lang, prob = transcriber.transcribe(audio)
    print(f'[STT] text="{text}" lang={lang} p={prob:.2f} t={time.time() - t0:.2f} s', flush=True)

    if not text:
        return llm_parser._reject("empty")
    if lang != "en" and prob >= NON_EN_MIN_PROB:
        result = llm_parser._reject("non-English")
        chat_interface.remember(text, result, history)
        return result
    return chat_interface.handle_utterance(text, history, queue)
