# -*- coding: utf-8 -*-
"""把 knowledge-base 里的 Markdown 条目打包成一个可双击打开的本地浏览页 index.html。
用法: python kb-build.py
"""
import os, re, json, datetime
from pathlib import Path
import markdown

KB = r"E:\deepseek\knowledge-base"
OUT = os.path.join(KB, "index.html")

md = markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists"])


def parse(path):
    raw = open(path, encoding="utf-8-sig").read()
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
    v = meta.get("标签", "").strip().strip("[]")
    return [t.strip() for t in re.split(r"[,，]", v) if t.strip()]


def fix_image_extensions(root):
    """纠正扩展名与真实格式不符的图片（浏览器会判定为损坏），并同步改 md 引用。"""
    renamed = 0
    for md in list(root.glob("wechat/*.md")):
        text = md.read_text(encoding="utf-8-sig")
        original = text
        for ref in set(re.findall(r"!\[[^\]]*\]\((\.\./_assets/[^)]+)\)", text)):
            p = (md.parent / ref).resolve()
            if not p.exists():
                continue
            head = p.read_bytes()[:16]
            real = None
            if head[:3] == b"\xff\xd8\xff":
                real = ".jpg"
            elif head[:8] == b"\x89PNG\r\n\x1a\n":
                real = ".png"
            elif head[:6] in (b"GIF87a", b"GIF89a"):
                real = ".gif"
            elif head[:4] == b"RIFF" and head[8:12] == b"WEBP":
                real = ".webp"
            if real and real != p.suffix.lower():
                new = p.with_suffix(real)
                if new.exists():
                    p.unlink()
                else:
                    p.rename(new)
                text = text.replace(p.name, new.name)
                renamed += 1
        if text != original:
            md.write_text(text, encoding="utf-8")
    if renamed:
        print("fixed %d image extensions" % renamed)


def summary_of(body):
    m = re.search(r"##\s*一句话总结\s*\n+(.+?)(?:\n##|\Z)", body, re.S)
    if m:
        t = m.group(1).strip()
        if "待提炼" not in t:
            return re.sub(r"\s+", " ", t)[:160]
    txt = re.sub(r"```.*?```", "", body, flags=re.S)
    txt = re.sub(r"[#>*\-]", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()[:160]


def render(body):
    body = body.replace("](../_assets/", "](_assets/")
    md.reset()
    return md.convert(body)


fix_image_extensions(Path(KB))

def short_source(type_name):
    t = type_name or ""
    if t.startswith("抖音"):
        return "抖音视频"
    if t.startswith("公众号"):
        return "微信公众号"
    if t.startswith("小红书"):
        return "小红书"
    if t.startswith("哔哩哔哩") or t.startswith("B站"):
        return "B站"
    return "笔记"


entries = []
for sub in ("douyin", "bili", "wechat", "xhs", "notes"):
    d = os.path.join(KB, sub)
    if not os.path.isdir(d):
        continue
    for name in sorted(os.listdir(d)):
        if not name.endswith(".md"):
            continue
        meta, body = parse(os.path.join(d, name))
        raw_title = meta.get("视频标题") or meta.get("原文标题") or meta.get("标题") or name[:-3]
        src = short_source(meta.get("类型", sub))
        entries.append({
            "type": meta.get("类型", sub),
            "src": src,
            "title": "【%s】%s" % (src, raw_title),
            "raw_title": raw_title,
            "source": meta.get("原链接", ""),
            "author": meta.get("作者", "") or meta.get("公众号名称", ""),
            "date": meta.get("入库时间", ""),
            "publish": meta.get("发布时间", ""),
            "tags": tags_of(meta),
            "summary": summary_of(body),
            "html": render(body),
            "file": "%s/%s" % (sub, name),
        })

entries.sort(key=lambda e: e["date"], reverse=True)
built = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
data = json.dumps(entries, ensure_ascii=False)

TPL_PATH = Path(__file__).resolve().parent / "viewer-template.html"
TEMPLATE = TPL_PATH.read_text(encoding="utf-8-sig") if TPL_PATH.exists() else "<html><body>缺少 viewer-template.html</body></html>"

page = TEMPLATE.replace("__DATA__", data).replace("__BUILT__", built)
open(OUT, "w", encoding="utf-8").write(page)
print("OK", OUT, len(page), "bytes,", len(entries), "entries")