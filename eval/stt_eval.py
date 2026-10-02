"""
eval/stt_eval.py — STUDENT B OWNS THIS FILE. Bonus: speech-input evaluation.

Interactive: prompts you to SPEAK each utterance (a real human voice — no
TTS), records it with the same push-to-talk recorder as the chat loop,
transcribes it with faster-whisper, parses the transcript with the current
llm_parser, and scores the parsed command with the SAME checker as the typed
Task 3 eval (eval/task3_eval.py CASES).

    eval/run_env.sh eval/stt_eval.py              # record + score (~12 utterances)
    eval/run_env.sh eval/stt_eval.py --rescore eval/results/stt/<session>
                                                  # re-score saved WAVs, no microphone
    eval/run_env.sh eval/stt_eval.py --report eval/results/stt/<session>.jsonl
                                                  # rebuild the md only, no API calls

WAVs go to eval/results/stt/<session>/ (git-ignored: voice recordings are
not committed); per-utterance results to eval/results/stt/<session>.jsonl;
the summary table to eval/stt_eval.md.
"""

import argparse
import json
import re
import sys
import time
import wave
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import config  # noqa: E402
from dialogue import llm_parser, speech_input  # noqa: E402
from eval.task3_eval import CASES  # noqa: E402

STT_DIR = Path(__file__).resolve().parent / "results" / "stt"
REPORT = Path(__file__).resolve().parent / "stt_eval.md"

# 10 English commands (incl. the multi-step reference M1 and an invalid one)
# + 2 non-English. Ids and checkers come from the typed Task 3 eval.
DEFAULT_IDS = ["B1", "B3", "B5", "M1", "M3", "P3", "P5", "L1", "L2", "X1", "X2", "X3"]
NON_ENGLISH = {"X2": "French", "X3": "Mandarin"}

_NUM = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five",
        "6": "six", "7": "seven", "8": "eight", "9": "nine", "10": "ten",
        "45": "forty five", "90": "ninety", "180": "one eighty"}


def _norm_words(s: str):
    s = s.lower().replace("-", " ").replace("°", " degrees ")
    s = re.sub(r"[^\w\s]", " ", s)
    return [w for tok in s.split() for w in _NUM.get(tok, tok).split()]


def _edit_distance(a, b) -> int:
    d = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(b) + 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (a[i - 1] != b[j - 1]))
    return d[len(b)]


def error_rate(ref: str, hyp: str, cid: str):
    """WER for English; character error rate for Mandarin; WER for French."""
    if cid == "X3":
        r = [c for c in ref if c.strip() and c not in "，。！？,.!?"]
        h = [c for c in hyp if c.strip() and c not in "，。！？,.!?"]
        return "CER", _edit_distance(r, h) / max(len(r), 1)
    r, h = _norm_words(ref), _norm_words(hyp)
    return "WER", _edit_distance(r, h) / max(len(r), 1)


def save_wav(path: Path, audio: np.ndarray):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(speech_input.SAMPLE_RATE)
        w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())


def load_wav(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768.0


def score(case, audio, transcriber):
    """Same steps as speech_input.handle_voice, timed, without the queue."""
    cid, cat, setup, ref, check = case
    t0 = time.time()
    text, lang, prob = transcriber.transcribe(audio) if audio.size else ("", "-", 0.0)
    t_stt = time.time() - t0
    if not text:
        result = llm_parser._reject("empty")
    elif lang != "en" and prob >= speech_input.NON_EN_MIN_PROB:
        result = llm_parser._reject("non-English")
    else:
        result = llm_parser.parse_command(text, [])
    t_total = time.time() - t0
    ok, why = check(result)
    metric, err = error_rate(ref, text, cid)
    return dict(id=cid, category=cat, reference=ref, transcript=text, lang=lang,
                lang_prob=round(prob, 3), metric=metric, error_rate=round(err, 3),
                accepted=result.accepted, reject_reason=result.reject_reason,
                actions=json.loads(llm_parser.history_entry(result)),
                parse_ok=bool(ok), why=why, audio_s=round(audio.size / speech_input.SAMPLE_RATE, 2),
                stt_s=round(t_stt, 3), stt_llm_s=round(t_total, 3),
                llm_called=bool(text) and not (lang != "en" and prob >= speech_input.NON_EN_MIN_PROB))


def _row_ok(r) -> bool:
    """English: the parsed command passes the typed-eval checker (X1 "fly to
    the roof" passes if it is transcribed and then rejected by the parser).
    Non-English: rejected as non-English, by language ID or by the LLM."""
    if r["id"] in NON_ENGLISH:
        return (not r["accepted"]) and r["reject_reason"] == "non-English"
    return r["parse_ok"]


def write_report(rows, session, analysis: str = ""):
    eng = [r for r in rows if r["id"] not in NON_ENGLISH]
    non = [r for r in rows if r["id"] in NON_ENGLISH]
    stt = sorted(r["stt_s"] for r in rows if r["audio_s"])
    llm = sorted(r["stt_llm_s"] for r in rows if r["llm_called"])
    med = lambda xs: xs[len(xs) // 2] if xs else float("nan")
    ref_words = sum(len(_norm_words(r["reference"])) for r in eng)
    errors = sum(round(r["error_rate"] * len(_norm_words(r["reference"]))) for r in eng)
    lines = [
        "# Bonus — speech input (STT) evaluation", "",
        f"Session `{session}`. **One speaker** (the project author), the laptop's built-in microphone, "
        "room noise about −41 dBFS, push-to-talk recorder from `dialogue/speech_input.py`. "
        f"STT: faster-whisper `{speech_input.WHISPER_MODEL}`, local on the GPU (CUDA float16); parser: "
        f"`{config.LLM_SERVICE}` with the current prompt, no history. Every transcript is scored with the "
        "same checker as the typed Task 3 eval (`eval/task3_eval.py`). The recordings stay local in "
        f"`eval/results/stt/{session}/` (git-ignored); per-utterance metrics are in "
        f"`eval/results/stt/{session}.jsonl`.", "",
        "Scoring: English rows pass if the parsed command passes the typed-eval checker; X1 "
        "(\"fly to the roof\") passes if it is transcribed and then rejected by the parser. "
        "Non-English rows (X2 French, X3 Mandarin) are scored only as *rejected as non-English: "
        "yes/no* and are left out of the WER.", "",
        "## Summary", "",
        f"- English utterances handled correctly: **{sum(_row_ok(r) for r in eng)}/{len(eng)}**",
        f"- Non-English rejected as non-English: **{sum(_row_ok(r) for r in non)}/{len(non)}**",
        f"- English word error rate (pooled over {len(eng)} utterances): **{100 * errors / max(ref_words, 1):.1f}%** "
        f"({errors} word errors / {ref_words} reference words; digits are normalised, so "
        "\"3 seconds\" = \"three seconds\")",
        f"- English utterances identified as English: **{sum(r['lang'] == 'en' for r in eng)}/{len(eng)}**, "
        f"p = {min(r['lang_prob'] for r in eng):.2f}–{max(r['lang_prob'] for r in eng):.2f}",
        f"- Latency, median: STT **{med(stt):.2f} s**; STT + LLM **{med(llm):.2f} s** (over the "
        f"{len(llm)} utterances that reached the LLM). Measured from the end of recording, so it "
        "excludes the 1 s of silence the recorder waits for.",
        "", "## Per utterance", "",
        "| Id | Reference | Transcript | lang / p | WER | Parsed OK | STT s | STT+LLM s |",
        "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r["id"] in NON_ENGLISH:
            how = ("language ID" if not r["llm_called"] else "LLM")
            ok = (f"rejected as non-English: {'yes' if _row_ok(r) else 'no'}"
                  + (f" (by {how})" if _row_ok(r) else f" ({r['reject_reason'] or 'accepted'})"))
            wer = "n/a"
            ref = f"{r['reference']} ({NON_ENGLISH[r['id']]})"
        else:
            got = (f"rejected: {r['actions']['reason']}" if "rejected" in r["actions"]
                   else ", ".join(a["action"] for a in r["actions"]["actions"]))
            ok = f"{'✅' if _row_ok(r) else '❌'} {got}"
            wer = f"{100 * r['error_rate']:.0f}%"
            ref = r["reference"]
        stt_llm = f"{r['stt_llm_s']:.2f}" if r["llm_called"] else f"{r['stt_llm_s']:.2f} (no LLM)"
        lines.append(f"| {r['id']} | {ref} | {r['transcript'] or '—'} | {r['lang']} / {r['lang_prob']:.2f} | "
                     f"{wer} | {ok} | {r['stt_s']:.2f} | {stt_llm} |")
    if analysis:
        lines += ["", "## Failure analysis", "", analysis.strip()]
    REPORT.write_text("\n".join(lines) + "\n")
    print(f"wrote {REPORT}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", nargs="+", default=DEFAULT_IDS)
    ap.add_argument("--rescore", type=Path, help="re-score the WAVs in this session folder")
    ap.add_argument("--report", type=Path, metavar="SESSION_JSONL",
                    help="rebuild eval/stt_eval.md from a results file (no mic, no API calls)")
    ap.add_argument("--analysis", type=Path, help="markdown file with the failure analysis")
    args = ap.parse_args()
    analysis = args.analysis.read_text() if args.analysis else ""
    if args.report:
        rows = [json.loads(l) for l in args.report.open()]
        write_report(rows, args.report.stem, analysis)
        return
    cases = {c[0]: c for c in CASES}
    transcriber = speech_input.get_transcriber()
    transcriber.transcribe(np.zeros(16000, np.float32))   # load + warm up before timing

    if args.rescore:
        session = args.rescore.name
        rows = [score(cases[cid], load_wav(args.rescore / f"{cid}.wav"), transcriber)
                for cid in args.cases if (args.rescore / f"{cid}.wav").is_file()]
    else:
        session = datetime.now().strftime("%Y%m%d-%H%M%S")
        rows = []
        print(f"\n{len(args.cases)} utterances. For each: press Enter, then say the sentence "
              "naturally. Recording stops ~1 s after you finish.\n")
        for i, cid in enumerate(args.cases, 1):
            ref = cases[cid][3]
            lang = NON_ENGLISH.get(cid, "English")
            while True:
                cmd = input(f"[{i}/{len(args.cases)}] ({lang}) say: \"{ref}\"   "
                            "[Enter = record, s = skip] ").strip().lower()
                if cmd == "s":
                    break
                audio = speech_input.record()
                row = score(cases[cid], audio, transcriber)
                print(f"   heard: \"{row['transcript']}\" ({row['lang']} {row['lang_prob']:.2f})  "
                      f"{row['metric']} {100 * row['error_rate']:.0f}%  parse "
                      f"{'OK' if row['parse_ok'] else 'FAIL: ' + row['why']}")
                if input("   Enter = keep, r = record again ").strip().lower() != "r":
                    save_wav(STT_DIR / session / f"{cid}.wav", audio)
                    rows.append(row)
                    break
    out = STT_DIR / f"{session}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {out}")
    write_report(rows, session, analysis)


if __name__ == "__main__":
    main()
