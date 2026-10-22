# -*- coding: utf-8 -*-
"""给条目加「来源」标注：正文开头一行 > 来源：… ｜ 原链接：…，并给 INDEX.md 标题加【来源】前缀。
用法: python kb-tag-source.py
"""
import os
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

KB = Path(os.environ.get("KB_HOME") or r"E:\deepseek\knowledge-base")

SHORT = {
    "抖音视频": "抖音视频",
    "公众号文章": "微信公众号",
    "公众号图文（分享页）": "微信公众号",
    "公众号图文（图片消息）": "微信公众号",
    "公众号图文": "微信公众号",
    "对比笔记": "笔记",
    "笔记": "笔记",
}


def short_of(type_name):
    for k, v in SHORT.items():
        if type_name.startswith(k):
            return v
    return type_name or "笔记"


def frontmatter(text):
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", text, re.S)
    if not m:
        return {}, None, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, m, text


def tag_entry(md):
    text = md.read_text(encoding="utf-8-sig")
    meta, m, _ = frontmatter(text)
    if not meta:
        return False
    src = short_of(meta.get("类型", ""))
    url = meta.get("原链接", "")
    line = "> 来源：%s%s" % (src, ("　｜　原链接：%s" % url) if url else "")
    body = m.group(2)
    if body.lstrip().startswith("> 来源："):
        return False
    new = text[:m.end(1)] + "\n\n" + line + "\n" + body
    md.write_text(new, encoding="utf-8")
    return True


def tag_index():
    idx = KB / "INDEX.md"
    if not idx.exists():
        return 0
    lines = idx.read_text(encoding="utf-8-sig").splitlines()
    out, n = [], 0
    for line in lines:
        if line.startswith("|") and line.count("|") >= 6 and "---" not in line and "入库时间" not in line:
            cols = [c.strip() for c in line.strip("|").split("|")]
            if len(cols) >= 3 and not cols[2].startswith("【"):
                prefix = "【%s】" % ("抖音视频" if cols[1] == "抖音视频" else
                                    "微信公众号" if cols[1].startswith("公众号") else "笔记")
                cols[2] = prefix + cols[2]
                line = "| " + " | ".join(cols) + " |"
                n += 1
        out.append(line)
    idx.write_text("\n".join(out) + "\n", encoding="utf-8")
    return n


def main():
    changed = 0
    for sub in ("douyin", "wechat", "notes"):
        d = KB / sub
        if not d.is_dir():
            continue
        for md in sorted(d.glob("*.md")):
            if tag_entry(md):
                changed += 1
    print("条目加来源标注:", changed)
    print("索引标题加前缀:", tag_index())


if __name__ == "__main__":
    main()
