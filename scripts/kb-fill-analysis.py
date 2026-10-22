# -*- coding: utf-8 -*-
"""把分析稿写回条目：替换「一句话总结/核心内容/金句/图片」占位块。"""
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

md = Path(sys.argv[1])
analysis = Path(sys.argv[2]).read_text(encoding="utf-8").strip()
text = md.read_text(encoding="utf-8-sig")

# 定位占位块：从「## 一句话总结」到「## 图片」或「## 原文」之前（保留图片段）
start = text.find("## 一句话总结")
end = text.find("## 图片（已存档）")
if end < 0:
    end = text.find("## 图片")
if end < 0:
    end = text.find("## 原文")
if start < 0 or end < 0:
    sys.exit("找不到占位块: %s" % md)
text = text[:start] + analysis + "\n\n" + text[end:]
text = text.replace("> （待识别图片内容）", "> 原文配图")
md.write_text(text, encoding="utf-8")
print("已写回:", md.name, len(text), "字")
