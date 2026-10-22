# -*- coding: utf-8 -*-
"""小红书笔记入库：分享链接 → 标题/正文/图片/标签 → 知识库条目。

用法: python kb-ingest-xhs.py "https://xhslink.cn/o/xxxx"
依赖: requests
"""
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

KB = Path(os.environ.get("KB_HOME") or r"E:\deepseek\knowledge-base")
UA_MOBILE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
             "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
UA_PC = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def load_state(html):
    m = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{.*)", html, re.S)
    if not m:
        return None
    raw = m.group(1).replace("undefined", "null")
    depth, end = 0, None
    for i, ch in enumerate(raw):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    try:
        return json.loads(raw[:end])
    except Exception:
        return None


def main(share_url):
    s = requests.Session()
    s.headers.update({"User-Agent": UA_MOBILE, "Referer": "https://www.xiaohongshu.com/"})
    r = s.get(share_url, timeout=30, allow_redirects=True)
    r.encoding = "utf-8"
    final_url = r.url
    state = load_state(r.text)
    if not state:
        sys.exit("解析失败：页面里没有 __INITIAL_STATE__（可能需要登录或链接已失效）")

    note = (((state.get("noteData") or {}).get("data") or {}).get("noteData") or {})
    if not note:
        note = ((state.get("normalNotePreloadData") or {}).get("noteData") or {})
    if not note:
        sys.exit("解析失败：没有拿到笔记内容")

    note_id = note.get("noteId") or final_url.rstrip("/").split("/")[-1].split("?")[0]
    title = (note.get("title") or "").strip() or "小红书笔记 " + str(note_id)
    desc = (note.get("desc") or "").strip()
    author = ((note.get("user") or {}).get("nickName") or "").strip()
    ts = note.get("time")
    ptime = datetime.datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M") if ts else ""

    adir = KB / "_assets" / "xhs" / str(note_id)
    adir.mkdir(parents=True, exist_ok=True)

    img_lines, seen = [], set()
    for u in (note.get("imageList") or []):
        url = u.get("urlDefault") or u.get("urlPre") or u.get("url") or ""
        if not url or url in seen:
            continue
        seen.add(url)
        try:
            rr = s.get(url, timeout=30, headers={"Referer": "https://www.xiaohongshu.com/"})
            if rr.status_code != 200 or len(rr.content) < 5000:
                continue
            magic = rr.content[:16]
            ext = (".png" if magic[:8] == b"\x89PNG\r\n\x1a\n" else
                   ".webp" if magic[:4] == b"RIFF" and magic[8:12] == b"WEBP" else
                   ".gif" if magic[:6] in (b"GIF87a", b"GIF89a") else ".jpg")
            name = "img_%02d%s" % (len(img_lines) + 1, ext)
            (adir / name).write_bytes(rr.content)
            img_lines.append("![图片](../_assets/xhs/%s/%s)\n> 原文配图" % (note_id, name))
        except Exception:
            pass

    # 话题标签
    tags = []
    for t in re.findall(r"#([^\s#\[\]]{1,20})", desc):
        if t not in tags:
            tags.append(t)
    tag_line = ", ".join(tags)

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    pt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    md = KB / "xhs" / ("%s.md" % note_id)
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text("""---
类型: 小红书笔记
笔记ID: %s
标题: %s
原链接: %s
作者: %s
发布时间: %s
解析时间: %s
入库时间: %s
标签: [%s]
---

> 来源：小红书　｜　原链接：%s

## 一句话总结
（待提炼）

## 核心内容
（待提炼）

## 原文正文

%s

## 图片（已存档）
%s

## 资源清单

## 对我的价值 / 可复用点
（待提炼）
""" % (note_id, title, final_url, author, ptime, pt, now, tag_line, final_url, desc,
       "\n\n".join(img_lines)), encoding="utf-8")
    (adir / "note.txt").write_text(desc, encoding="utf-8")

    idx = KB / "INDEX.md"
    lines = idx.read_text(encoding="utf-8-sig").splitlines()
    row = "| %s | 小红书笔记 | 【小红书】%s | %s | %s | [条目](xhs/%s.md) |" % (
        now, title, "/".join(tags) if tags else "待补", final_url, note_id)
    out, inserted = [], False
    for line in lines:
        if "(xhs/%s.md)" % note_id in line:
            continue
        out.append(line)
        if not inserted and re.match(r"^\|[-|]+\|$", line):
            out.append(row)
            inserted = True
    idx.write_text("\n".join(out) + "\n", encoding="utf-8")

    print(json.dumps({"note_id": note_id, "title": title, "author": author,
                      "publish": ptime, "images": len(img_lines), "md": str(md)},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python kb-ingest-xhs.py <分享链接>")
        sys.exit(1)
    main(sys.argv[1])
