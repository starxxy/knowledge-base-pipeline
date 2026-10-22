# -*- coding: utf-8 -*-
"""公众号「分享页 / 图片消息」入库兜底：这类页面没有 js_content，正文需在微信内打开。
本脚本取 og:title / og:description + 页面图片，归档成条目（类型：公众号图文）。
用法: python kb-ingest-wechat-share.py <文章URL>
"""
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

KB = Path(os.environ.get("KB_HOME") or r"E:\deepseek\knowledge-base")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def main(url):
    r = requests.get(url, headers={"User-Agent": UA, "Referer": "https://mp.weixin.qq.com/"}, timeout=30)
    r.encoding = "utf-8"
    html = r.text

    def meta(prop):
        m = re.search(r'property="%s" content="([^"]*)"' % prop, html, re.S)
        return m.group(1).strip() if m else ""

    title = meta("og:title") or "未命名图文"
    desc = meta("og:description").replace("\\x0a", "\n").replace("\x0a", "\n").strip()
    aid = url.rstrip("/").split("/")[-1].split("?")[0]
    adir = KB / "_assets" / "wechat" / aid
    adir.mkdir(parents=True, exist_ok=True)

    urls = re.findall(r'cdn_url\s*[:=]\s*["\'](https?://[^"\']+)["\']', html)
    if not urls:
        urls = re.findall(r'(https?://mmbiz\.qpic\.cn/[^"\'\s\\)]+)', html)
    seen, lines, saved = set(), [], 0
    for u in urls:
        u = u.replace("\\x26", "&").replace("\\/", "/")
        key = u.split("?")[0]
        if key in seen:
            continue
        seen.add(key)
        try:
            rr = requests.get(u, headers={"User-Agent": UA, "Referer": url}, timeout=25)
            if rr.status_code != 200 or len(rr.content) < 3000:
                continue
            magic = rr.content[:16]
            ext = (".png" if magic[:8] == b"\x89PNG\r\n\x1a\n" else
                   ".gif" if magic[:6] in (b"GIF87a", b"GIF89a") else
                   ".webp" if magic[:4] == b"RIFF" and magic[8:12] == b"WEBP" else ".jpg")
            name = "img_%02d%s" % (saved + 1, ext)
            (adir / name).write_bytes(rr.content)
            lines.append("![图片](../_assets/wechat/%s/%s)\n> 分享页配图" % (aid, name))
            saved += 1
        except Exception:
            pass

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    pt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    md = KB / "wechat" / (aid + ".md")
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text("""---
类型: 公众号图文（分享页）
公众号名称:
原文标题: %s
原文链接: %s
作者:
发布时间:
解析时间: %s
入库时间: %s
标签: []
---

> 来源：微信公众号　｜　原链接：%s

## 一句话总结
（待提炼）

## 核心内容
（待提炼）

## 图片（已存档）
%s

## 原文（分享页简介）

%s

## 资源清单

## 对我的价值 / 可复用点
（待提炼）
""" % (title, url, pt, now, url, "\n\n".join(lines), desc), encoding="utf-8")
    (adir / "article.txt").write_text(desc, encoding="utf-8")

    idx = KB / "INDEX.md"
    lines_idx = idx.read_text(encoding="utf-8").splitlines()
    row = "| %s | 公众号图文 | 【微信公众号】%s | 待补 | %s | [条目](wechat/%s.md) |" % (now, title, url, aid)
    out, inserted = [], False
    for line in lines_idx:
        if "(wechat/%s.md)" % aid in line:
            continue
        out.append(line)
        if not inserted and re.match(r"^\|[-|]+\|$", line):
            out.append(row)
            inserted = True
    idx.write_text("\n".join(out) + "\n", encoding="utf-8")

    subprocess.run([r"D:\Python312\python.exe", r"E:\deepseek\kb-tools\kb-build.py"],
                   check=False, capture_output=True, timeout=300)
    print(json.dumps({"title": title, "images": saved, "md": str(md)}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python kb-ingest-wechat-share.py <url>")
        sys.exit(1)
    main(sys.argv[1])
