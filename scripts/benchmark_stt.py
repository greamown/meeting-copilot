#!/usr/bin/env python3
import argparse
import json
import subprocess
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark faster-whisper load time and real-time factor")
    parser.add_argument("audio", nargs="?", help="16 kHz mono audio fixture; omit to test model load only")
    parser.add_argument("--model", default="large-v3-turbo")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--compute-type", default="float16")
    parser.add_argument("--stability-minutes", type=int, default=5)
    args = parser.parse_args()
    from faster_whisper import WhisperModel
    before = gpu_memory()
    started = time.perf_counter(); model = WhisperModel(args.model, device=args.device, compute_type=args.compute_type); load_seconds = time.perf_counter() - started
    result = {"model": args.model, "device": args.device, "compute_type": args.compute_type, "load_seconds": round(load_seconds, 3), "gpu_memory_before_mb": before}
    if args.audio:
        audio = Path(args.audio).resolve(); duration = probe_duration(audio); started = time.perf_counter(); segments, _ = model.transcribe(str(audio), vad_filter=True, beam_size=5); text = "".join(segment.text for segment in segments); elapsed = time.perf_counter() - started; result.update({"audio_seconds": duration, "transcribe_seconds": round(elapsed, 3), "real_time_factor": round(elapsed / duration, 4), "characters": len(text)})
        deadline = time.monotonic() + args.stability_minutes * 60; passes = 0
        while time.monotonic() < deadline: list(model.transcribe(str(audio), vad_filter=True)[0]); passes += 1
        result["stability_passes"] = passes
    result["gpu_memory_after_mb"] = gpu_memory(); result["peak_gpu_delta_mb"] = max(0, result["gpu_memory_after_mb"] - before)
    output = Path("runtime/stt-benchmark.json"); output.parent.mkdir(exist_ok=True); output.write_text(json.dumps(result, indent=2)); print(json.dumps(result, indent=2))


def gpu_memory() -> int:
    try: return int(subprocess.check_output(["nvidia-smi", "--query-compute-apps=used_memory", "--format=csv,noheader,nounits"], text=True).splitlines()[0])
    except (OSError, subprocess.SubprocessError, IndexError, ValueError): return 0


def probe_duration(path: Path) -> float:
    output = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)], text=True); return float(output.strip())


if __name__ == "__main__": main()
