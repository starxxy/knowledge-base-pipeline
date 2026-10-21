# -*- coding: utf-8 -*-
"""清理知识库 _assets 里重复保存的图片：同内容只保留最早一张，并把条目里的引用改过去。
用法: python kb-dedupe-assets.py
"""
import hashlib
import os
import re
import sys
from pathlib import Path

KB = Path(os.environ.get("KB_HOME") or r"E:\deepseek\knowledge-base")
ASSETS = KB / "_assets"


def md5(p):
    return hashlib.md5(p.read_bytes()).hexdigest()


def clean_dir(dirpath, entry_md):
    groups = {}
    for f in sorted(dirpath.glob("img_*")):
        groups.setdefault(md5(f), []).append(f)
    removed, rewritten = 0, 0
    rename = {}
    for h, files in groups.items():
        if len(files) < 2:
            continue
        keep = files[0]
        for dup in files[1:]:
            rename[dup.name] = keep.name
        # 先改正文引用，再删除重复文件
        if entry_md.exists():
            text = entry_md.read_text(encoding="utf-8")
            changed = text
            for dup in files[1:]:
                changed = changed.replace(dup.name, keep.name)
            if changed != text:
                entry_md.write_text(changed, encoding="utf-8")
                rewritten += 1
        for dup in files[1:]:
            dup.unlink()
            removed += 1
    return removed, rewritten


def main():
    total_removed = total_fixed = 0
    for d in sorted((KB / "_assets").glob("*/*")):
        if not d.is_dir():
            continue
        aid = d.name
        entry_md = KB / "wechat" / (aid + ".md")
        if not entry_md.exists():
            continue
        removed, rewritten = clean_dir(d, entry_md)
        if removed:
            print("%s: removed %d, md fixed %d" % (aid, removed, rewritten))
        total_removed += removed
        total_fixed += rewritten
    print("DONE removed=%d md_fixed=%d" % (total_removed, total_fixed))


if __name__ == "__main__":
    main()