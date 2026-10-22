# 公众号入库流水线：文章链接 → 全文 + 图片存档 + 条目草稿 + 索引
# 用法: python wechat-ingest.py <文章URL>
import sys, re, os, html, json, datetime, urllib.parse
import requests
from bs4 import BeautifulSoup

try:  # 控制台可能是 GBK，避免标题里的特殊字符导致 print 崩溃
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

def main(url):
    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    kb = r"E:\deepseek\knowledge-base"
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    r = s.get(url, timeout=30)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "lxml")

    def meta(prop):
        m = soup.find("meta", property=prop)
        return m["content"] if m else ""

    title = meta("og:title")
    author = meta("og:article:author")
    m = re.search(r'data-nickname="([^"]+)"', r.text)
    account = html.unescape(m.group(1)) if m else ""
    ct = re.search(r'var ct = "?(\d{10})"?', r.text)
    ptime = datetime.datetime.fromtimestamp(int(ct.group(1))).strftime("%Y-%m-%d %H:%M") if ct else ""

    content = soup.find("div", id="js_content")
    if not content:
        print("正文未找到（可能被删除/需登录）"); sys.exit(1)
    plain = content.get_text("\n", strip=True)
    plain = re.sub(r"\n{3,}", "\n\n", plain)

    aid = url.rstrip("/").split("/")[-1].split("?")[0]
    adir = os.path.join(kb, "_assets", "wechat", aid)
    os.makedirs(adir, exist_ok=True)

    # 图片：按 URL 去重 + 按内容哈希去重（同一张图反复出现只保存一次）
    import hashlib
    url_map, seen_hash, saved = {}, {}, []
    for im in content.find_all("img"):
        u = im.get("data-src") or im.get("src") or ""
        if not u.startswith("http"):
            continue
        key = u.split("?")[0] if "mmbiz.qpic.cn" in u else u   # 公众号图参数只是格式变体，按路径去重
        url_map.setdefault(key, u)
    for i, u in enumerate(url_map.values(), 1):
        try:
            rr = s.get(u, timeout=20, headers={"Referer": url})
            if rr.status_code == 200 and len(rr.content) > 1000:
                digest = hashlib.md5(rr.content).hexdigest()
                if digest in seen_hash:          # 同内容图片已保存过，复用引用
                    saved.append(seen_hash[digest])
                    continue
                ext = os.path.splitext(u.split("?")[0])[1].lower() or ".jpg"
                if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
                    ext = ".jpg"
                # 以真实字节为准（公众号常见：URL 写 jpg、内容其实是 png/webp）
                magic = rr.content[:16]
                if magic[:8] == b"\x89PNG\r\n\x1a\n":
                    ext = ".png"
                elif magic[:3] == b"\xff\xd8\xff":
                    ext = ".jpg"
                elif magic[:6] in (b"GIF87a", b"GIF89a"):
                    ext = ".gif"
                elif magic[:4] == b"RIFF" and magic[8:12] == b"WEBP":
                    ext = ".webp"
                name = "img_%02d%s" % (i, ext)
                open(os.path.join(adir, name), "wb").write(rr.content)
                seen_hash[digest] = name
                saved.append(name)
        except Exception:
            pass
    saved = list(dict.fromkeys(saved))  # 去重引用但保持顺序

    # 视频（记录元数据 + 封面）
    video_info = []
    for v in content.find_all("iframe"):
        if "mpvideo" in (v.get("class") or []) or v.get("data-mpvid"):
            cover = urllib.parse.unquote(v.get("data-cover", "") or "")
            cname = ""
            if cover:
                try:
                    rr = s.get(cover, timeout=20, headers={"Referer": url})
                    if rr.status_code == 200 and len(rr.content) > 5000:
                        cname = "video_cover.jpg"
                        open(os.path.join(adir, cname), "wb").write(rr.content)
                except Exception:
                    pass
            video_info.append({"mpvid": v.get("data-mpvid", ""), "cover": cname})

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    pt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 文末话题标签 -> 知识库标签（排除 HEX 色值，如 #EE6B0D）
    tags = []
    for t in re.findall(r"#([^\s#]{1,20})", plain):
        if re.fullmatch(r"[0-9A-Fa-f]{3,8}", t):
            continue
        if t not in tags:
            tags.append(t)
    tag_line = ", ".join(tags)
    tag_index = "/".join(tags) if tags else "待补"
    md = os.path.join(kb, "wechat", aid + ".md")
    os.makedirs(os.path.dirname(md), exist_ok=True)

    img_lines = []
    for name in saved:
        rel = "../_assets/wechat/%s/%s" % (aid, name)
        img_lines.append("![图片](../_assets/wechat/%s/%s)\n> （待识别图片内容）" % (aid, name))

    video_lines = []
    for v in video_info:
        video_lines.append("- 视频号视频（`%s`），封面：![视频封面](../_assets/wechat/%s/video_cover.jpg)" % (v["mpvid"], aid) if v.get("cover") else "- 视频号视频（`%s`）" % v["mpvid"])

    with open(md, "w", encoding="utf-8") as f:
        f.write("""---
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

> 来源：微信公众号　｜　原链接：%s

## 一句话总结
（待提炼）

## 核心内容
（待提炼）

## 图片（已存档 + 内容识别）
%s

## 视频
%s

## 原文全文

%s

## 对我的价值 / 可复用点
（待提炼）
""" % (account, title, url, author, ptime, pt, now, tag_line, url, "\n\n".join(img_lines), "\n".join(video_lines) or "（无）", plain))

    # 索引：插在表头分隔线之后，保持倒序；重跑时先删旧行
    idx = os.path.join(kb, "INDEX.md")
    row = "| %s | 公众号文章 | 【微信公众号】%s | %s | %s | [条目](wechat/%s.md) |" % (now, title, tag_index, url, aid)
    lines = open(idx, encoding="utf-8").read().splitlines()
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
    open(idx, "w", encoding="utf-8").write("\n".join(out) + "\n")

    # 重建本地浏览页（桌面「个人知识库」快捷方式打开的那个）
    try:
        import subprocess
        subprocess.run([r"D:\Python312\python.exe", r"E:\deepseek\kb-tools\kb-build.py"],
                       check=False, capture_output=True, timeout=120)
        # 增量同步到 NAS 上的思源笔记
        subprocess.run([r"D:\Python312\python.exe", r"E:\deepseek\kb-tools\kb-import-siyuan.py"],
                       check=False, capture_output=True, timeout=300)
        # 视觉去重：同一张图（不同格式/带水印重复）只保留一张
        subprocess.run([r"D:\Python312\python.exe", r"E:\deepseek\kb-tools\kb-dedupe-visual.py"],
                       check=False, capture_output=True, timeout=300)
    except Exception:
        pass

    print(json.dumps({"title": title, "account": account, "author": author,
                      "publish": ptime, "images": len(saved), "videos": len(video_info),
                      "md": md}, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python wechat-ingest.py <url>"); sys.exit(1)
    main(sys.argv[1])