# -*- coding: utf-8 -*-
"""按「视觉内容」去重知识库里的图片：同一张图（含不同格式/不同压缩）只保留一张，
并同步修正条目里的引用。删除的文件会先移到 _recycle 目录（可人工找回）。

用法: python kb-dedupe-visual.py [--dry-run]
"""
import hashlib
import os
import re
import shutil
import sys
from pathlib import Path

from PIL import Image

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

KB = Path(os.environ.get("KB_HOME") or r"E:\deepseek\knowledge-base")
RECYCLE = Path(os.environ.get("TEMP", ".")) / "kb_recycle"
THRESHOLD = 3  # 汉明距离阈值：<=3 视为同一张图


def ahash(path, size=8):
    try:
        img = Image.open(path).convert("L").resize((size, size), Image.LANCZOS)
    except Exception:
        return None
    px = list(img.getdata())
    avg = sum(px) / len(px)
    bits = 0
    for i, p in enumerate(px):
        if p > avg:
            bits |= 1 << i
    return bits


def thumb(path, size=32):
    """返回 (像素列表, 宽高比)；用于像素级确认，避免把'同模板不同内容'误判成重复。"""
    try:
        img = Image.open(path).convert("L")
        ratio = img.width / max(1, img.height)
        small = img.resize((size, size), Image.LANCZOS)
        return list(small.getdata()), ratio
    except Exception:
        return None, None


def mad(a, b):
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def same_visual(f1, h1, t1, r1, f2, h2, t2, r2, threshold):
    if ham(h1, h2) > threshold:
        return False
    if abs(r1 - r2) > 0.03:          # 宽高比差 >3% 直接判为不同
        return False
    return mad(t1, t2) < 8           # 像素平均差 <8/255 才认为同一张


def ham(a, b):
    return bin(a ^ b).count("1")


def process_folder(folder, md_path, dry_run):
    files = sorted([f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in
                    (".jpg", ".jpeg", ".png", ".gif", ".webp")])
    items = []
    for f in files:
        h = ahash(f)
        if h is None:
            continue
        t, r = thumb(f)
        if t is None:
            continue
        items.append((f, h, t, r))

    keep, dup_map = [], {}
    for f, h, t, r in items:
        hit = None
        for kf, kh, kt, kr in keep:
            if same_visual(f, h, t, r, kf, kh, kt, kr, THRESHOLD):
                hit = kf
                break
        if hit is None:
            keep.append((f, h, t, r))
        else:
            dup_map[f.name] = hit.name

    if not dup_map:
        return 0
    if "--list" in sys.argv or dry_run:
        for dup, canon in sorted(dup_map.items()):
            print("   %s  ==  %s" % (dup, canon))

    # 改引用（先改名再删文件）
    if md_path.exists():
        text = md_path.read_text(encoding="utf-8")
        new = text
        for dup, canon in dup_map.items():
            new = new.replace(dup, canon)
        # 同一张图重复引用多行时去掉多余空行
        new = re.sub(r"\n{3,}", "\n\n", new)
        if new != text and not dry_run:
            md_path.write_text(new, encoding="utf-8")

    if not dry_run:
        dest = RECYCLE / folder.name
        dest.mkdir(parents=True, exist_ok=True)
        for dup in dup_map:
            src = folder / dup
            if src.exists():
                shutil.move(str(src), str(dest / dup))
    return len(dup_map)


def main():
    dry = "--dry-run" in sys.argv
    total = 0
    for sub in KB.glob("_assets/*/*"):
        if not sub.is_dir():
            continue
        aid = sub.name
        md = KB / "wechat" / (aid + ".md")
        n = process_folder(sub, md, dry)
        if n:
            print("%s: 合并 %d 张重复图片" % (aid, n))
            total += n
    print("%s 共处理重复图片 %d 张（回收站：%s）" % ("DRY-RUN" if dry else "DONE", total, RECYCLE))


if __name__ == "__main__":
    main()
