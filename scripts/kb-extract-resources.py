# -*- coding: utf-8 -*-
"""从条目逐字稿里抽取「资源清单」候选：网址、工具/产品名、人名、开源仓库。
用法:
  python kb-extract-resources.py                 # 扫描全部抖音条目，输出候选
  python kb-extract-resources.py <条目路径>       # 只扫一条
说明：语音转写里通常没有网址，工具名靠词典 + 拉丁词频启发式；结果需要 AI 复核。
"""
import os
import re
import sys
from collections import Counter
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

KB = Path(os.environ.get("KB_HOME") or r"E:\deepseek\knowledge-base")

# 常见 AI / 开发 / 工具词典（可继续补充）
KNOWN = [
    "WorkBuddy", "CodeBuddy", "Codex", "Claude Code", "Claude", "Cursor", "Copilot", "Windsurf",
    "OpenCode", "Codebuff", "Freebuff", "OpenClaw", "Hermes", "Qoder", "Trae", "Lingma", "通义灵码",
    "DeepSeek", "豆包", "千问", "Qwen", "Kimi", "GLM", "智谱", "MiniMax", "MiMo", "Hunyuan", "混元",
    "GPT", "ChatGPT", "Gemini", "Grok", "Sora", "Midjourney", "Stable Diffusion", "ComfyUI",
    "Suno", "Seedance", "可灵", "即梦", "Vidu", "Runway", "Pika", "HeyGen", "剪映", "CapCut",
    "Blender", "Photoshop", "Figma", "Illustrator", "Sketch", "Canva",
    "n8n", "Zapier", "Make", "Dify", "Coze", "扣子", "FastGPT", "RAGFlow", "AnythingLLM",
    "Obsidian", "Notion", "Logseq", "思源", "SiYuan", "Flomo", "Memos", "Karakeep", "Hoarder",
    "GitHub", "Gitea", "GitLab", "Docker", "Coolify", "Vercel", "Supabase", "Cloudflare",
    "PostgreSQL", "Redis", "MySQL", "MongoDB", "Meilisearch", "Uptime Kuma", "frp", "Orbien",
    "Whisper", "faster-whisper", "FFmpeg", "yt-dlp", "Playwright", "Puppeteer", "MCP", "AutoGLM",
    "AutoClaw", "Miora", "WeSight", "WeChatBridge", "Kwai", "小红书", "抖音", "视频号", "B站",
]

URL_RE = re.compile(r"https?://[^\s，。）)]+")
LATIN_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9.+#-]{1,20}\b")
CN_HINT = re.compile(r"(工具|软件|平台|网站|应用|App|插件|开源|模型|框架|仓库|官网|地址|教程)")


def resources_of(md_path):
    text = md_path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"## 逐字稿（全文）\s*\n```+\n(.*?)\n```+", text, re.S)
    body = m.group(1) if m else text

    urls = sorted(set(URL_RE.findall(body)))

    found = []
    low = body.lower()
    for name in KNOWN:
        if name.lower() in low and name not in found:
            found.append(name)

    # 拉丁词频：出现在「工具/平台/开源」等提示词附近的词更可能是产品名
    hints = Counter()
    for line in body.splitlines():
        if CN_HINT.search(line):
            for w in LATIN_RE.findall(line):
                if len(w) >= 3 and not w.islower():
                    hints[w] += 1
    return urls, found, hints.most_common(12)


def main():
    targets = [Path(sys.argv[1])] if len(sys.argv) > 1 else sorted((KB / "douyin").glob("*.md"))
    for md in targets:
        urls, found, hints = resources_of(md)
        title = ""
        m = re.search(r"^视频标题:\s*(.+)$", md.read_text(encoding="utf-8-sig"), re.M)
        if m:
            title = m.group(1).strip()
        print("=" * 60)
        print("%s\n  %s" % (md.name, title[:70]))
        print("  词典命中 : %s" % ("、".join(found) if found else "（无）"))
        print("  网址     : %s" % ("、".join(urls[:6]) if urls else "（转写里没有网址）"))
        print("  疑似候选 : %s" % ("、".join(w for w, _ in hints) if hints else "（无）"))


if __name__ == "__main__":
    main()
