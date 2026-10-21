# -*- coding: utf-8 -*-
"""把知识库里的 Markdown 打包成一个可双击打开的本地浏览页 index.html。

用法: python kb-build.py
特点：单文件、零依赖（打开即用）、支持搜索与标签筛选、图片走相对路径。
"""
import datetime
import json
import os
import re
from pathlib import Path

import markdown

CONFIG = {}
try:
    _cfg = Path(__file__).resolve().parent.parent / "config.json"
    if _cfg.exists():
        CONFIG = json.loads(_cfg.read_text(encoding="utf-8-sig"))
except Exception:
    CONFIG = {}

KB = Path(os.environ.get("KB_HOME") or CONFIG.get("kb_home") or (Path.home() / "knowledge-base"))
OUT = KB / "index.html"
MD = markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists"])


def parse(path):
    raw = path.read_text(encoding="utf-8-sig")
    meta, body = {}, raw
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", raw, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        body = m.group(2)
    return meta, body


def tags_of(meta):
    return [t.strip() for t in re.split(r"[,，]", meta.get("标签", "").strip().strip("[]")) if t.strip()]


def summary_of(body):
    m = re.search(r"##\s*一句话总结\s*\n+(.+?)(?:\n##|\Z)", body, re.S)
    if m and "待提炼" not in m.group(1):
        return re.sub(r"\s+", " ", m.group(1).strip())[:160]
    txt = re.sub(r"```.*?```", "", body, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"[#>*\-]", " ", txt)).strip()[:160]


def render(body):
    MD.reset()
    return MD.convert(body.replace("](../_assets/", "](_assets/"))


entries = []
for sub in ("douyin", "wechat", "notes"):
    d = KB / sub
    if not d.is_dir():
        continue
    for f in sorted(d.glob("*.md")):
        meta, body = parse(f)
        entries.append({
            "type": meta.get("类型", sub),
            "title": meta.get("视频标题") or meta.get("原文标题") or meta.get("标题") or f.stem,
            "source": meta.get("原链接", ""),
            "author": meta.get("作者", "") or meta.get("公众号名称", ""),
            "date": meta.get("入库时间", ""),
            "publish": meta.get("发布时间", ""),
            "tags": tags_of(meta),
            "summary": summary_of(body),
            "html": render(body),
            "file": "%s/%s" % (sub, f.name),
        })

entries.sort(key=lambda e: e["date"], reverse=True)
built = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
template = (Path(__file__).resolve().parent.parent / "viewer" / "template.html")
html = template.read_text(encoding="utf-8-sig") if template.exists() else "<html><body>缺少 viewer/template.html</body></html>"
html = html.replace("__DATA__", json.dumps(entries, ensure_ascii=False)).replace("__BUILT__", built)
OUT.write_text(html, encoding="utf-8")
print("OK %s (%d entries, %d bytes)" % (OUT, len(entries), len(html)))
