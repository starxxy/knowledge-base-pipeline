# -*- coding: utf-8 -*-
"""把 INDEX.md 里标签为「待补」的行，替换成条目 frontmatter 里的真实标签。"""
import os
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

KB = Path(os.environ.get("KB_HOME") or r"E:\deepseek\knowledge-base")
idx = KB / "INDEX.md"
text = idx.read_text(encoding="utf-8-sig")
out, fixed = [], 0
for line in text.splitlines():
    if line.startswith("|") and "待补" in line:
        m = re.search(r"\]\((\w+)/([^)]+)\)", line)
        if m:
            md = KB / m.group(1) / m.group(2)
            if md.exists():
                head = md.read_text(encoding="utf-8-sig")[:800]
                t = re.search(r"^标签:\s*\[(.*?)\]\s*$", head, re.M)
                if t and t.group(1).strip():
                    tags = "/".join(x.strip() for x in re.split(r"[,，]", t.group(1)) if x.strip())
                    line = line.replace("| 待补 |", "| %s |" % tags)
                    fixed += 1
    out.append(line)
idx.write_text("\n".join(out) + "\n", encoding="utf-8")
print("索引标签补全:", fixed)
