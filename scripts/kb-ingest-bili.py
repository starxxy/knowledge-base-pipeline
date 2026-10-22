# -*- coding: utf-8 -*-
"""B 站视频入库：分享链接 → 标题/UP主/时长 → 下载视频 → GPU 转写 → 条目 + 索引。

用法: python kb-ingest-bili.py "https://b23.tv/xxxx"
依赖: yt-dlp、ffmpeg、faster-whisper（走 kb-tools/transcribe.py）
"""
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

KB = Path(os.environ.get("KB_HOME") or r"E:\deepseek\knowledge-base")
MEDIA = Path(os.environ.get("KB_MEDIA") or r"Z:\douyin-media")
TOOLS = Path(r"E:\deepseek\kb-tools")
PYTHON = r"D:\Python312\python.exe"
YTDLP = r"D:\Python312\Scripts\yt-dlp.exe"


def run(cmd, timeout=None):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="ignore", timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def main(url):
    # 1. 元信息
    rc, out, err = run([YTDLP, "--no-warnings", "--dump-json", "--no-playlist", url], timeout=120)
    if rc != 0 or not out.strip():
        sys.exit("yt-dlp 取元信息失败: %s" % (err or out)[:300])
    info = json.loads(out.strip().splitlines()[0])
    vid = info.get("id") or ""
    title = (info.get("title") or "").strip()
    uploader = (info.get("uploader") or info.get("channel") or "").strip()
    duration = info.get("duration") or 0
    pub = info.get("upload_date") or ""
    pub = "%s-%s-%s" % (pub[:4], pub[4:6], pub[6:8]) if len(pub) == 8 else ""
    desc = (info.get("description") or "").strip()

    safe = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", title)[:80].strip().rstrip(".")
    MEDIA.mkdir(parents=True, exist_ok=True)
    target = MEDIA / ("%s.mp4" % safe)
    if target.exists() and target.stat().st_size > 10000:
        print("视频已存在，跳过下载:", target)
    else:
        rc, out, err = run([YTDLP, "--no-warnings", "-f", "bv*+ba/b", "--merge-output-format", "mp4",
                            "-o", str(target), url], timeout=3600)
        if rc != 0 or not target.exists():
            sys.exit("下载失败: %s" % (err or out)[:300])

    # 2. 抽音频 + 转写
    audio = KB / "_media" / ("%s.mp3" % vid)
    (KB / "_media").mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-y", "-v", "error", "-i", str(target), "-vn", "-acodec", "libmp3lame", "-q:a", "4", str(audio)],
        timeout=1800)
    transcript_file = Path(os.environ.get("TEMP", ".")) / ("transcript_%s.txt" % vid)
    if transcript_file.exists():
        transcript_file.unlink()
    rc, out, err = run([PYTHON, str(TOOLS / "transcribe.py"), str(audio), str(transcript_file)], timeout=7200)
    if not transcript_file.exists():
        sys.exit("转写失败: %s" % (err or out)[:300])
    transcript = transcript_file.read_text(encoding="utf-8").strip()

    # 3. 条目
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    pt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    md = KB / "bili" / ("%s.md" % vid)
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text("""---
类型: 哔哩哔哩视频
视频ID: %s
视频标题: %s
原链接: %s
作者: %s
发布时间: %s
视频时长: %ss
解析时间: %s
入库时间: %s
NAS归档路径: %s
标签: []
---

> 来源：B站　｜　原链接：%s

## 一句话总结
（待提炼）

## 核心内容
（待提炼）

## 金句 / 可复用片段
（待提炼）

## 图片（已存档）

## 逐字稿（全文）
```
%s
```

## 元信息
- 视频原件: %s（%s bytes，%ss）
- 音轨: _media\\%s.mp3（转写用临时音频）
- 简介: %s
""" % (vid, title, url, uploader, pub, duration, pt, now, target, url, transcript,
       target, target.stat().st_size, duration, vid, desc[:300]), encoding="utf-8")

    idx = KB / "INDEX.md"
    lines = idx.read_text(encoding="utf-8-sig").splitlines()
    row = "| %s | 哔哩哔哩视频 | 【B站】%s | 待补 | %s | [条目](bili/%s.md) |" % (now, title, url, vid)
    outl, inserted = [], False
    for line in lines:
        if "(bili/%s.md)" % vid in line:
            continue
        outl.append(line)
        if not inserted and re.match(r"^\|[-|]+\|$", line):
            outl.append(row)
            inserted = True
    idx.write_text("\n".join(outl) + "\n", encoding="utf-8")

    print(json.dumps({"id": vid, "title": title, "uploader": uploader, "duration": duration,
                      "publish": pub, "chars": len(transcript), "md": str(md)},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python kb-ingest-bili.py <分享链接>")
        sys.exit(1)
    main(sys.argv[1])
