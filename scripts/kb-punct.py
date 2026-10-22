# -*- coding: utf-8 -*-
"""把条目里的逐字稿抽出到临时文件（供断句处理），或把处理结果写回条目。
用法:
  python kb-punct.py extract         # 导出到 %TEMP%\\punct\\<id>.txt，并打印每个文件的行数
  python kb-punct.py apply [id...]   # 把 %TEMP%\\punct\\<id>.fixed.txt 写回条目
"""
import os
import re
import sys
from pathlib import Path

KB = Path(os.environ.get("KB_HOME") or r"E:\deepseek\knowledge-base")
TMP = Path(os.environ.get("TEMP", ".")) / "punct"
FENCE = re.compile(r"## 逐字稿（全文）\s*\n`{3,}\n(.*?)\n`{3,}", re.S)


def entries():
    return sorted((KB / "douyin").glob("*.md"))


def extract():
    TMP.mkdir(parents=True, exist_ok=True)
    for md in entries():
        text = md.read_text(encoding="utf-8-sig")
        m = FENCE.search(text)
        if not m:
            print("%-28s 无逐字稿" % md.stem)
            continue
        body = m.group(1)
        out = TMP / (md.stem + ".txt")
        out.write_text(body, encoding="utf-8")
        print("%-28s %5d 行 -> %s" % (md.stem, len(body.splitlines()), out))


def apply(ids):
    for md in entries():
        if ids and md.stem not in ids:
            continue
        fixed = TMP / (md.stem + ".fixed.txt")
        if not fixed.exists():
            print("%s 缺少 %s，跳过" % (md.stem, fixed.name))
            continue
        text = md.read_text(encoding="utf-8-sig")
        m = FENCE.search(text)
        if not m:
            print("%s 无逐字稿，跳过" % md.stem)
            continue
        new_body = fixed.read_text(encoding="utf-8-sig").strip()
        text = text[:m.start(1)] + new_body + text[m.end(1):]
        md.write_text(text, encoding="utf-8")
        print("%s 已写回（%d 字）" % (md.stem, len(new_body)))


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "extract"
    if mode == "extract":
        extract()
    elif mode == "apply":
        apply(sys.argv[2:])
    else:
        print(__doc__)
