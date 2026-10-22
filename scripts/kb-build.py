# -*- coding: utf-8 -*-
"""把 knowledge-base 里的 Markdown 条目打包成一个可双击打开的本地浏览页 index.html。
用法: python kb-build.py
"""
import os, re, json, datetime
from pathlib import Path
import markdown

KB = r"E:\deepseek\knowledge-base"
OUT = os.path.join(KB, "index.html")

md = markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists"])


def parse(path):
    raw = open(path, encoding="utf-8").read()
    meta, body = {}, raw
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", raw, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        body = m.group(2)
    return meta, body


def tags_of(meta):
    v = meta.get("标签", "").strip().strip("[]")
    return [t.strip() for t in re.split(r"[,，]", v) if t.strip()]


def fix_image_extensions(root):
    """纠正扩展名与真实格式不符的图片（浏览器会判定为损坏），并同步改 md 引用。"""
    renamed = 0
    for md in list(root.glob("wechat/*.md")):
        text = md.read_text(encoding="utf-8")
        original = text
        for ref in set(re.findall(r"!\[[^\]]*\]\((\.\./_assets/[^)]+)\)", text)):
            p = (md.parent / ref).resolve()
            if not p.exists():
                continue
            head = p.read_bytes()[:16]
            real = None
            if head[:3] == b"\xff\xd8\xff":
                real = ".jpg"
            elif head[:8] == b"\x89PNG\r\n\x1a\n":
                real = ".png"
            elif head[:6] in (b"GIF87a", b"GIF89a"):
                real = ".gif"
            elif head[:4] == b"RIFF" and head[8:12] == b"WEBP":
                real = ".webp"
            if real and real != p.suffix.lower():
                new = p.with_suffix(real)
                if new.exists():
                    p.unlink()
                else:
                    p.rename(new)
                text = text.replace(p.name, new.name)
                renamed += 1
        if text != original:
            md.write_text(text, encoding="utf-8")
    if renamed:
        print("fixed %d image extensions" % renamed)


def summary_of(body):
    m = re.search(r"##\s*一句话总结\s*\n+(.+?)(?:\n##|\Z)", body, re.S)
    if m:
        t = m.group(1).strip()
        if "待提炼" not in t:
            return re.sub(r"\s+", " ", t)[:160]
    txt = re.sub(r"```.*?```", "", body, flags=re.S)
    txt = re.sub(r"[#>*\-]", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()[:160]


def render(body):
    body = body.replace("](../_assets/", "](_assets/")
    md.reset()
    return md.convert(body)


fix_image_extensions(Path(KB))

entries = []
for sub in ("douyin", "wechat", "notes"):
    d = os.path.join(KB, sub)
    if not os.path.isdir(d):
        continue
    for name in sorted(os.listdir(d)):
        if not name.endswith(".md"):
            continue
        meta, body = parse(os.path.join(d, name))
        title = meta.get("视频标题") or meta.get("原文标题") or meta.get("标题") or name[:-3]
        entries.append({
            "type": meta.get("类型", sub),
            "title": title,
            "source": meta.get("原链接", ""),
            "author": meta.get("作者", "") or meta.get("公众号名称", ""),
            "date": meta.get("入库时间", ""),
            "publish": meta.get("发布时间", ""),
            "tags": tags_of(meta),
            "summary": summary_of(body),
            "html": render(body),
            "file": "%s/%s" % (sub, name),
        })

entries.sort(key=lambda e: e["date"], reverse=True)
built = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
data = json.dumps(entries, ensure_ascii=False)

TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>个人知识库</title>
<style>
:root{
  --bg:#f1f4f9; --panel:#ffffff; --ink:#18202b; --muted:#64748b;
  --line:#e4e9f0; --accent:#3b6ef5; --accent-soft:#e8eefc;
  --card-shadow:0 1px 3px rgba(15,23,42,.06),0 8px 24px -12px rgba(15,23,42,.12);
  --radius:14px; --list-w:340px;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{font:15px/1.75 -apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--ink)}
button{font-family:inherit}
/* ---------- header ---------- */
header{position:sticky;top:0;z-index:30;background:rgba(255,255,255,.9);backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
.hwrap{max-width:1280px;margin:0 auto;padding:12px 18px;display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.hwrap.tight{padding-top:4px}
.logo{font-weight:700;font-size:17px;display:flex;align-items:center;gap:8px;white-space:nowrap}
.logo .dot{width:10px;height:10px;border-radius:3px;background:linear-gradient(135deg,var(--accent),#7c5cff);display:inline-block}
.logo small{font-weight:400;color:var(--muted);font-size:12px;margin-left:4px}
.search{flex:1;min-width:200px;position:relative}
.search input{width:100%;padding:9px 12px 9px 34px;border:1px solid var(--line);border-radius:10px;font-size:14px;outline:none;background:var(--bg);color:var(--ink)}
.search input:focus{border-color:var(--accent);background:#fff;box-shadow:0 0 0 3px var(--accent-soft)}
.search .icon{position:absolute;left:11px;top:50%;transform:translateY(-50%);color:var(--muted);font-size:14px}
#chips{display:flex;gap:6px;flex-wrap:wrap}
.chip{padding:2px 10px;border-radius:99px;background:var(--accent-soft);color:#2c4d9e;font-size:12px;cursor:pointer;border:1px solid transparent;user-select:none}
.chip.on{background:var(--accent);color:#fff}
/* ---------- layout ---------- */
.layout{max-width:1280px;margin:0 auto;display:grid;grid-template-columns:var(--list-w) 1fr}
#listPane{border-right:1px solid var(--line);overflow-y:auto;padding:12px;position:sticky;top:107px;height:calc(100vh - 107px)}
.item{padding:12px 14px;border-radius:12px;cursor:pointer;margin-bottom:8px;background:var(--panel);border:1px solid var(--line);transition:border-color .15s}
.item:hover{border-color:#b9c8f5}
.item.on{border-color:var(--accent);box-shadow:0 0 0 2px var(--accent-soft)}
.item .t{font-weight:600;font-size:14px;line-height:1.5}
.item .m{font-size:12px;color:var(--muted);margin-top:5px;display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.item .s{font-size:12px;color:var(--muted);margin-top:5px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.tag{background:#f1f5f9;color:#475569;border-radius:6px;padding:0 7px;font-size:11px}
/* ---------- reading ---------- */
#viewPane{overflow-y:auto;padding:26px 30px;height:calc(100vh - 107px);position:sticky;top:107px}
#viewPane article{max-width:860px;margin:0 auto;background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--card-shadow);padding:34px 40px 40px}
h1.doc-title{font-size:22px;line-height:1.4;margin:0 0 10px}
.meta{color:var(--muted);font-size:12.5px;display:flex;gap:14px;flex-wrap:wrap;margin:0 0 6px}
.meta a{color:var(--accent);text-decoration:none}
.meta a:hover{text-decoration:underline}
.divider{height:1px;background:var(--line);margin:16px 0 4px}
article h2{font-size:16px;margin:30px 0 12px;padding:0 0 8px;border-bottom:1px solid var(--line);color:#243b6b}
article h3{font-size:15px;margin:20px 0 8px}
article p{margin:10px 0}
article img{max-width:100%;border-radius:10px;border:1px solid var(--line);display:block;margin:12px auto}
article blockquote{margin:10px 0;padding:9px 15px;border-left:3px solid var(--accent);background:var(--accent-soft);border-radius:0 10px 10px 0;color:#3a4a6b;font-size:14px}
article pre{background:#101828;color:#dbe4f3;padding:16px;border-radius:10px;overflow:auto;font-size:12.5px;line-height:1.6;font-family:ui-monospace,Consolas,monospace}
article code{font-family:ui-monospace,Consolas,monospace}
article table{border-collapse:collapse;width:100%;font-size:13.5px;margin:12px 0}
article th,article td{border:1px solid var(--line);padding:7px 11px;text-align:left;vertical-align:top}
article th{background:#f5f7fb;font-weight:600}
article ul,article ol{padding-left:22px}
article li{margin:5px 0}
.tagrow{display:flex;gap:8px;flex-wrap:wrap;margin-top:4px}
.empty{color:var(--muted);text-align:center;padding:80px 20px;font-size:14px}
.empty b{color:var(--ink);font-size:16px;display:block;margin-bottom:8px}
/* ---------- mobile ---------- */
#backBtn{display:none;background:none;border:none;color:var(--accent);font-size:15px;padding:4px 0;cursor:pointer;margin-bottom:6px}
@media (max-width:900px){
  .layout{grid-template-columns:1fr}
  #listPane{position:static;height:auto;max-height:none;border-right:none;border-bottom:1px solid var(--line)}
  #viewPane{height:auto;padding:16px 14px 40px;display:none}
  #viewPane.show{display:block}
  #backBtn.show{display:inline-block}
  #viewPane article{padding:22px 18px 30px}
  .logo small{display:none}
}
@media (prefers-color-scheme:dark){
  :root{--bg:#0f1622;--panel:#161e2c;--ink:#e6eaf2;--muted:#94a3b8;--line:#26303f;--accent:#6d94ff;--accent-soft:#1d2a44;--card-shadow:0 1px 3px rgba(0,0,0,.4),0 10px 30px -12px rgba(0,0,0,.5)}
  .search input{background:#0c1220;color:var(--ink)}
  .search input:focus{background:#0f1727}
  article h2{color:#9db7ff}
  .tag{background:#1c2534;color:#a8b6cc}
  header{background:rgba(15,22,34,.92)}
}
</style>
</head>
<body>
<header>
  <div class="hwrap">
    <div class="logo"><span class="dot"></span>个人知识库<small id="count"></small></div>
    <div class="search"><span class="icon">🔍</span><input id="q" placeholder="搜索标题、正文、标签…"></div>
  </div>
  <div class="hwrap tight">
    <div id="chips" style="flex:1"></div>
  </div>
</header>
<div class="layout">
  <div id="listPane"><div id="list"></div></div>
  <div id="viewPane">
    <button id="backBtn">← 返回列表</button>
    <div id="content"><div class="empty"><b>知识库已就绪</b>点左侧任意条目开始阅读</div></div>
  </div>
</div>
<script>
const DATA=__DATA__;
const BUILT="__BUILT__";
const $=id=>document.getElementById(id);
const listEl=$('list'),contentEl=$('content'),viewPane=$('viewPane');
const qEl=$('q'),chipsEl=$('chips'),countEl=$('count'),backBtn=$('backBtn');
let activeTag=null,current=null;
const allTags=[...new Set(DATA.flatMap(e=>e.tags))];
chipsEl.innerHTML=allTags.map(t=>'<span class="chip" data-tag="'+t+'">'+t+'</span>').join('');
chipsEl.onclick=e=>{const c=e.target.closest('.chip');if(!c)return;activeTag=(activeTag===c.dataset.tag?null:c.dataset.tag);
  [...chipsEl.children].forEach(x=>x.classList.toggle('on',x.dataset.tag===activeTag));render();};
qEl.oninput=()=>render();
function match(e,q){if(!q)return true;return(e.title+' '+e.summary+' '+e.tags.join(' ')+' '+e.html.replace(/<[^>]+>/g,' ')).toLowerCase().includes(q);}
function render(){
  const q=qEl.value.trim().toLowerCase();
  const rows=DATA.filter(e=>(!activeTag||e.tags.includes(activeTag))&&match(e,q));
  countEl.textContent='共 '+DATA.length+' 条 · 当前 '+rows.length+' 条 · 更新于 '+BUILT;
  listEl.innerHTML=rows.map(e=>'<div class="item'+(current===e?' on':'')+'" data-i="'+DATA.indexOf(e)+'">'+
    '<div class="t">'+e.title+'</div><div class="m"><span>'+e.date+'</span><span>'+e.type+'</span>'+
    e.tags.slice(0,3).map(t=>'<span class="tag">'+t+'</span>').join('')+'</div>'+
    '<div class="s">'+e.summary+'</div></div>').join('')||'<div class="empty">没有匹配的条目</div>';
}
listEl.onclick=e=>{const it=e.target.closest('.item');if(!it)return;show(DATA[+it.dataset.i]);};
function show(e){
  current=e;render();
  contentEl.innerHTML='<article><h1 class="doc-title">'+e.title+'</h1>'+
    '<div class="meta"><span>'+e.type+'</span><span>入库 '+(e.date||'')+'</span>'+
    (e.author?'<span>'+e.author+'</span>':'')+(e.publish?'<span>发布 '+e.publish+'</span>':'')+'</div>'+
    '<div class="meta tagrow">'+e.tags.map(t=>'<span class="tag">'+t+'</span>').join(' ')+
    (e.source?'<a href="'+e.source+'" target="_blank" rel="noopener">打开原链接 ↗</a>':'')+'</div>'+
    '<div class="divider"></div><div class="body">'+e.html+'</div></article>';
  viewPane.scrollTop=0;window.scrollTo(0,0);
  if(window.innerWidth<=900){viewPane.classList.add('show');backBtn.classList.add('show');}
}
backBtn.onclick=()=>{viewPane.classList.remove('show');backBtn.classList.remove('show');window.scrollTo(0,0);};
render();
if(window.innerWidth>900&&DATA.length){show(DATA[0]);}
</script>
</body>
</html>
"""

page = TEMPLATE.replace("__DATA__", data).replace("__BUILT__", built)
open(OUT, "w", encoding="utf-8").write(page)
print("OK", OUT, len(page), "bytes,", len(entries), "entries")