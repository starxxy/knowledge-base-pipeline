# -*- coding: utf-8 -*-
"""公众号条目「原文全文」的断句/分段整理：
- 把被 <span>/<p> 切碎的行合并成完整句子与段落
- 去掉微信页面的界面噪音行（"继续滑动看下一个"等）
- 保留列表项、标题、代码块与空行结构
用法: python kb-normalize-wechat.py [--dry-run]
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

NOISE = [
    "预览时标签不可点", "继续滑动看下一个", "轻触阅读原文", "向上滑动看下一个",
    "微信扫一扫", "使用小程序", "取消", "允许", "知道了", "分析", "写留言",
    "长按识别二维码", "关注该公众号", "分享", "收藏", "赞", "在看", "已同步到看一看",
]
NOISE_RE = re.compile("|".join(re.escape(x) for x in NOISE))

END_RE = re.compile(r"[.。！？!?…；;：:”\"』」）)》】]$")
SOFT_END = ("，", "、", "（", "(", "：", "—", "-")
LIST_RE = re.compile(r"^\s*(?:[-*•●○▪▶]|▶|【?\d+[、.．)）]|[①-⑳]|[✅⚠️📌🎯💡🛠🚀📦🔒🖥🤖📈⚖️✨📄📚▲🔹🔸])")
CODE_FENCE = re.compile(r"^\s*```")
HEADING = re.compile(r"^\s*#{1,6}\s+")


def normalize(text):
    out = []
    lines = text.split("\n")
    in_code = False
    for raw in lines:
        line = raw.strip()
        if CODE_FENCE.match(raw):
            in_code = not in_code
            out.append(raw)
            continue
        if in_code:
            out.append(raw)
            continue
        if not line:
            if out and out[-1] != "":
                out.append("")
            continue
        if NOISE_RE.fullmatch(line) or (len(line) <= 12 and NOISE_RE.search(line)):
            continue

        if HEADING.match(raw) or LIST_RE.match(raw) or line.startswith("|"):
            out.append(line)
            continue

        # 合并：只在上一行明显是被硬换行切断时才接上
        if out:
            prev = out[-1]
            if (prev and not HEADING.match(prev) and not LIST_RE.match(prev)
                    and not prev.startswith("|") and not END_RE.search(prev)
                    and (len(prev) < 30 or prev.endswith(SOFT_END))):
                out[-1] = prev + line
                continue
        out.append(line)

    # 收拾多余空行
    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def process(md, dry):
    text = md.read_text(encoding="utf-8-sig")
    changed = False
    for header in ("## 原文全文", "## 原文（分享页简介）"):
        i = text.find(header)
        if i < 0:
            continue
        start = text.find("\n", i) + 1
        j = text.find("\n## ", start)
        end = len(text) if j < 0 else j
        body = text[start:end]
        new = normalize(body)
        if new.strip() != body.strip():
            text = text[:start] + new + "\n\n" + text[end:]
            changed = True
    if changed and not dry:
        md.write_text(text, encoding="utf-8")
    return changed


def main():
    dry = "--dry-run" in sys.argv
    n = 0
    for md in sorted((KB / "wechat").glob("*.md")):
        if process(md, dry):
            print("%s 需要整理" % md.stem)
            n += 1
    print("%s 共 %d 个条目" % ("DRY-RUN" if dry else "DONE", n))


if __name__ == "__main__":
    main()
