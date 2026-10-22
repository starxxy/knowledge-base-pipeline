# -*- coding: utf-8 -*-
"""修复条目结构：
1) 若条目缺少「## 图片（已存档）」但对应 _assets 目录里有图，则按目录重建图片段落（插在「## 原文」之前）
2) 去掉重复的「## 对我的价值 / 可复用点」空占位块（正文里已有价值段时）
用法: python kb-repair-entries.py [--dry-run]
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


def images_for(kind, aid):
    d = KB / "_assets" / kind / aid
    if not d.is_dir():
        return []
    files = sorted([f for f in d.iterdir() if f.is_file() and f.suffix.lower() in
                    (".jpg", ".jpeg", ".png", ".gif", ".webp")])
    return ["![图片](../_assets/%s/%s/%s)\n> 原文配图" % (kind, aid, f.name) for f in files]


def repair(md, kind, dry):
    aid = md.stem
    text = md.read_text(encoding="utf-8-sig")
    orig = text

    # 1) 补图片段
    has_img_section = "## 图片" in text
    imgs = images_for(kind, aid)
    if not has_img_section and imgs:
        anchor = text.find("## 原文")
        block = "## 图片（已存档）\n\n" + "\n\n".join(imgs) + "\n\n"
        if anchor < 0:
            text = text.rstrip() + "\n\n" + block
        else:
            text = text[:anchor] + block + text[anchor:]

    # 2) 去掉重复的「对我的价值」占位块
    parts = re.split(r"(?m)^## 对我的价值 / 可复用点\s*$", text)
    if len(parts) > 2:
        # 保留第一次出现（正文里的价值段），丢弃其余
        joined = parts[0] + "## 对我的价值 / 可复用点" + parts[1]
        tail = parts[1]
        # 去掉价值段之后多余的占位尾巴（只留到文件末尾的非占位内容）
        joined = re.sub(r"(?m)^（待提炼）\s*$", "", joined)
        text = joined
    text = re.sub(r"\n{4,}", "\n\n\n", text)

    if text != orig and not dry:
        md.write_text(text, encoding="utf-8")
    return text != orig


def main():
    dry = "--dry-run" in sys.argv
    n = 0
    for kind in ("wechat", "xhs", "douyin"):
        d = KB / kind
        if not d.is_dir():
            continue
        for md in sorted(d.glob("*.md")):
            if repair(md, kind, dry):
                print("修复:", md.name)
                n += 1
    print("%s 共修复 %d 个条目" % ("DRY-RUN" if dry else "DONE", n))


if __name__ == "__main__":
    main()
