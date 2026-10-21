# -*- coding: utf-8 -*-
"""语音转文字：faster-whisper。

用法: python transcribe.py <audio_path> <output.txt> [--model large-v3] [--device cuda]
默认读 config.json 的 whisper_model / whisper_device，也可用环境变量
KB_WHISPER_MODEL / KB_WHISPER_DEVICE 覆盖。
"""
import json
import os
import sys
import time
from pathlib import Path


def load_config():
    cfg_path = Path(__file__).resolve().parent.parent / "config.json"
    if cfg_path.exists():
        try:
            return json.loads(cfg_path.read_text(encoding="utf-8-sig"))
        except Exception:
            return {}
    return {}


def main(audio, out):
    cfg = load_config()
    model_name = os.environ.get("KB_WHISPER_MODEL") or cfg.get("whisper_model") or "large-v3"
    device = os.environ.get("KB_WHISPER_DEVICE") or cfg.get("whisper_device") or "cuda"
    compute = cfg.get("whisper_compute_type") or ("float16" if device == "cuda" else "int8")

    # Windows 上 torch 的 DLL 目录有时不在 PATH 里
    try:
        import torch  # noqa: F401
        torch_lib = Path(torch.__file__).parent / "lib"
        if torch_lib.exists():
            os.environ["PATH"] = str(torch_lib) + os.pathsep + os.environ.get("PATH", "")
    except Exception:
        pass

    from faster_whisper import WhisperModel

    t0 = time.time()
    model = WhisperModel(model_name, device=device, compute_type=compute)
    segments, _info = model.transcribe(
        audio,
        language=cfg.get("whisper_language") or "zh",
        vad_filter=False,                 # VAD 依赖 onnxruntime，缺省关闭
        beam_size=1,                      # 比默认 beam=5 快约 35%，中文质量差异很小
        condition_on_previous_text=False,  # 降低长音频复读概率
    )
    text = "\n".join(s.text.strip() for s in segments if s.text.strip())
    Path(out).write_text(text.strip() + "\n", encoding="utf-8")
    print("DONE %d chars in %.1fs" % (len(text), time.time() - t0))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python transcribe.py <audio> <output.txt>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
