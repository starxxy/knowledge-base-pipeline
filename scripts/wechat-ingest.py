# -*- coding: utf-8 -*-
"""公众号文章入库：链接 → 正文 + 图片存档 + 条目草稿 + 索引。

用法: python wechat-ingest.py <文章URL>
如果直抓被「环境异常」拦截，会提示改用浏览器兜底（见 README）。
"""
import datetime
import json
import os
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CONFIG = {}
try:
    _cfg = Path(__file__).resolve().parent.parent / "config.json"
    if _cfg.exists():
        CONFIG = json.loads(_cfg.read_text(encoding="utf-8-sig"))
except Exception:
    CONFIG = {}

KB = os.environ.get("KB_HOME") or CONFIG.get("kb_home") or str(Path.home() / "knowledge-base")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def fetch(url):
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Referer": "https://mp.weixin.qq.com/"})
    r = session.get(url, timeout=30)
    r.encoding = "utf-8"
    return session, r.text


def main(url):
    session, html = fetch(url)
    soup = BeautifulSoup(html, "lxml")

    def meta(prop):
        m = soup.find("meta", property=prop)
        return (m.get("content") or "").strip() if m else ""

    title = meta("og:title") or (soup.title.get_text(strip=True) if soup.title else "")
    author = meta("og:article:author")
    m = re.search(r'data-nickname="([^"]+)"', html)
    account = m.group(1) if m else ""
    ct = re.search(r'var ct = "?(\d{10})"?', html)
    ptime = datetime.datetime.fromtimestamp(int(ct.group(1))).strftime("%Y-%m-%d %H:%M") if ct else ""

    content = soup.find("div", id="js_content")
    if not content:
        print("正文未找到：可能需要验证码/登录，或该链接是分享页。"
              "换一个 User-Agent 重试，或改用浏览器兜底方案。")
        sys.exit(2)

    plain = re.sub(r"\n{3,}", "\n\n", content.get_text("\n", strip=True))
    aid = url.rstrip("/").split("/")[-1].split("?")[0]
    adir = Path(KB) / "_assets" / "wechat" / aid
    adir.mkdir(parents=True, exist_ok=True)

    # 图片
    img_lines = []
    for i, im in enumerate(content.find_all("img"), 1):
        u = im.get("data-src") or im.get("src") or ""
        if not u.startswith("http"):
            continue
        try:
            rr = session.get(u, timeout=20, headers={"Referer": url})
            if rr.status_code == 200 and len(rr.content) > 1000:
                ext = ".png" if ("png" in u.lower() or "png" in rr.headers.get("content-type", "")) else ".jpg"
                if "gif" in u.lower():
                    ext = ".gif"
                if "webp" in u.lower():
                    ext = ".webp"
                name = "img_%02d%s" % (i, ext)
                (adir / name).write_bytes(rr.content)
                img_lines.append("![图片](../_assets/wechat/%s/%s)\n> 原文配图" % (aid, name))
        except Exception:
            pass

    # 话题标签 → 知识库标签
    tags = []
    for t in re.findall(r"#([^\s#]{1,20})", plain):
        if t not in tags:
            tags.append(t)
    tag_line = ", ".join(tags)

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    pt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    md_path = Path(KB) / "wechat" / (aid + ".md")
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("""---
类型: 公众号文章
公众号名称: %s
原文标题: %s
原文链接: %s
作者: %s
发布时间: %s
解析时间: %s
入库时间: %s
标签: [%s]
---

## 一句话总结
（待提炼）

## 核心内容
（待提炼）

## 金句 / 可复用片段
（待提炼）

## 图片（已存档）
%s

## 原文全文

%s

## 对我的价值 / 可复用点
（待提炼）
""" % (account, title, url, author, ptime, pt, now, tag_line, "\n\n".join(img_lines), plain),
        encoding="utf-8")

    # 索引（插在表头下，保持倒序；重跑先删旧行）
    index = Path(KB) / "INDEX.md"
    if not index.exists():
        index.write_text("# 知识库总索引\n\n| 入库时间 | 类型 | 标题 | 标签 | 原链接 | 条目 |\n|---|---|---|---|---|---|\n",
                         encoding="utf-8")
    tag_index = "/".join(tags) if tags else "待补"
    row = "| %s | 公众号文章 | %s | %s | %s | [条目](wechat/%s.md) |" % (now, title, tag_index, url, aid)
    lines = index.read_text(encoding="utf-8-sig").splitlines()
    out, inserted = [], False
    for line in lines:
        if "(wechat/%s.md)" % aid in line:
            continue
        out.append(line)
        if not inserted and re.match(r"^\|[-|]+\|$", line):
            out.append(row)
            inserted = True
    if not inserted:
        out.append(row)
    index.write_text("\n".join(out) + "\n", encoding="utf-8")

    print(json.dumps({"title": title, "account": account, "author": author, "publish": ptime,
                      "images": len(img_lines), "md": str(md_path)}, ensure_ascii=False, indent=1))
    print("下一步：读正文回填「一句话总结 / 核心内容 / 金句 / 对我的价值」，再跑 kb-build.py")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python wechat-ingest.py <url>")
        sys.exit(1)
    main(sys.argv[1])
