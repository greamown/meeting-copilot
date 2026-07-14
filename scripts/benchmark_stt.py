#!/usr/bin/env python3
import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path


def gpu_memory() -> int:
    try:
        rows = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-compute-apps=used_memory",
                "--format=csv,noheader,nounits",
            ],
            text=True,
        ).splitlines()
        return sum(int(row.strip()) for row in rows if row.strip())
    except (OSError, subprocess.SubprocessError, ValueError):
        return 0


def probe_duration(path: Path) -> float:
    output = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        text=True,
    )
    return float(output.strip())


def word_error_rate(reference: str, hypothesis: str) -> float | None:
    expected, actual = reference.split(), hypothesis.split()
    if not expected:
        return None
    previous = list(range(len(actual) + 1))
    for index, word in enumerate(expected, 1):
        current = [index]
        for offset, candidate in enumerate(actual, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[offset] + 1,
                    previous[offset - 1] + (word != candidate),
                )
            )
        previous = current
    return round(previous[-1] / len(expected), 4)


def synthetic_fixture(seconds: int) -> Path:
    path = Path(tempfile.gettempdir()) / "meeting-copilot-stt-benchmark.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:sample_rate=16000:duration={seconds}",
            "-ac",
            "1",
            "-y",
            str(path),
        ],
        check=True,
    )
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark faster-whisper on the configured GPU")
    parser.add_argument("audio", nargs="?", help="Audio fixture available inside the STT container")
    parser.add_argument("--model", default="large-v3-turbo")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--compute-type", default="float16")
    parser.add_argument("--language", default=None)
    parser.add_argument("--reference", help="Expected transcript used to calculate word error rate")
    parser.add_argument("--synthetic-seconds", type=int, default=30)
    parser.add_argument("--stability-minutes", type=int, choices=(0, 5, 30), default=0)
    args = parser.parse_args()

    from faster_whisper import WhisperModel

    before = gpu_memory()
    peak = before
    started = time.perf_counter()
    model = WhisperModel(args.model, device=args.device, compute_type=args.compute_type)
    load_seconds = time.perf_counter() - started
    peak = max(peak, gpu_memory())
    audio = Path(args.audio).resolve() if args.audio else synthetic_fixture(args.synthetic_seconds)
    duration = probe_duration(audio)
    started = time.perf_counter()
    segments, info = model.transcribe(
        str(audio), language=args.language, vad_filter=True, beam_size=5
    )
    text = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
    elapsed = time.perf_counter() - started
    peak = max(peak, gpu_memory())

    deadline = time.monotonic() + args.stability_minutes * 60
    passes = 0
    errors = 0
    while time.monotonic() < deadline:
        try:
            list(model.transcribe(str(audio), language=args.language, vad_filter=True)[0])
            passes += 1
            peak = max(peak, gpu_memory())
        except Exception:
            errors += 1

    result = {
        "model": args.model,
        "device": args.device,
        "compute_type": args.compute_type,
        "detected_language": getattr(info, "language", None),
        "load_seconds": round(load_seconds, 3),
        "audio_seconds": round(duration, 3),
        "transcribe_seconds": round(elapsed, 3),
        "real_time_factor": round(elapsed / duration, 4),
        "peak_gpu_memory_mb": peak,
        "peak_gpu_delta_mb": max(0, peak - before),
        "stability_minutes": args.stability_minutes,
        "stability_passes": passes,
        "stability_errors": errors,
        "word_error_rate": word_error_rate(args.reference, text) if args.reference else None,
        "characters": len(text),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
