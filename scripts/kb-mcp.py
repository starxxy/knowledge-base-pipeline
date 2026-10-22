#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""知识库 MCP 服务器（stdio）+ CLI。

MCP 用法（Claude Code / Codex / Cursor / DSH 等）：
  python kb-mcp.py            # stdio 模式，注册到客户端的 mcpServers 里
CLI 用法（任何 agent 都能用）：
  python kb-mcp.py --cli search "关键词" [--type 抖音视频] [--limit 5]
  python kb-mcp.py --cli get "douyin/7690890624584731930.md"
  python kb-mcp.py --cli list [--type wechat]
  python kb-mcp.py --cli stats

环境变量 KB_HOME 可覆盖知识库根目录（默认 E:\\deepseek\\knowledge-base）。
"""
import json
import os
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

KB = Path(os.environ.get("KB_HOME") or r"E:\deepseek\knowledge-base")
SUBS = ("douyin", "bili", "wechat", "xhs", "notes")
PROTOCOL = "2024-11-05"


def parse_md(p):
    raw = p.read_text(encoding="utf-8-sig", errors="ignore")
    meta, body = {}, raw
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", raw, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        body = m.group(2)
    title = (meta.get("视频标题") or meta.get("原文标题") or meta.get("标题") or p.stem).strip()
    tags = [t.strip() for t in re.split(r"[,，]", (meta.get("标签") or "").strip().strip("[]")) if t.strip()]
    return {
        "path": p.relative_to(KB).as_posix(),
        "title": title,
        "type": meta.get("类型", p.parent.name),
        "date": meta.get("入库时间", ""),
        "source": meta.get("原链接", ""),
        "author": meta.get("作者", "") or meta.get("公众号名称", ""),
        "tags": tags,
        "body": body,
    }


def all_entries():
    out = []
    for sub in SUBS:
        d = KB / sub
        if d.is_dir():
            out += [parse_md(p) for p in sorted(d.glob("*.md"))]
    return sorted(out, key=lambda e: e["date"], reverse=True)


def snippet(body, q, n=200):
    low, ql = body.lower(), (q or "").lower()
    i = low.find(ql) if ql else 0
    s = body[max(0, i - 40): i + n] if i >= 0 else body[:n]
    return re.sub(r"\s+", " ", s).strip()


def do_search(args):
    q = (args.get("query") or "").strip()
    t = args.get("type")
    limit = int(args.get("limit") or 10)
    res = []
    for e in all_entries():
        hay = (e["title"] + " " + " ".join(e["tags"]) + " " + e["body"]).lower()
        if (not q or q.lower() in hay) and (not t or t in e["type"]):
            r = {k: e[k] for k in ("path", "title", "type", "date", "tags", "author")}
            r["snippet"] = snippet(e["body"], q)
            res.append(r)
            if len(res) >= limit:
                break
    return {"count": len(res), "results": res}


def do_get(args):
    key = (args.get("path") or "").strip()
    if not key:
        raise ValueError("缺少 path")
    p = (KB / key).resolve()
    if KB.resolve() not in p.parents:
        raise ValueError("路径越界")
    if not p.exists():
        # 允许用文件名后缀模糊匹配
        for e in all_entries():
            if e["path"].endswith(key) or Path(e["path"]).stem == key:
                p = KB / e["path"]
                break
    if not p.exists():
        raise ValueError("条目不存在: %s" % key)
    e = parse_md(p)
    return {"path": e["path"], "title": e["title"], "type": e["type"], "date": e["date"],
            "source": e["source"], "tags": e["tags"], "content": e["body"].strip()}


def do_list(args):
    t = args.get("type")
    return {"count": 0, "results": [
        {k: e[k] for k in ("path", "title", "type", "date", "tags")}
        for e in all_entries() if not t or t in e["type"]]}


def do_stats(args):
    entries = all_entries()
    by_type = {}
    for e in entries:
        by_type[e["type"]] = by_type.get(e["type"], 0) + 1
    return {"total": len(entries), "by_type": by_type, "root": str(KB)}


TOOLS = {
    "kb_search": {
        "description": "在个人知识库里检索（标题/标签/正文全文匹配）。返回条目路径、标题、来源类型、日期、标签和片段。",
        "inputSchema": {"type": "object", "properties": {
            "query": {"type": "string", "description": "关键词"},
            "type": {"type": "string", "description": "可选，限定来源：抖音视频/哔哩哔哩视频/微信公众号/小红书/笔记"},
            "limit": {"type": "number", "description": "返回条数，默认 10"}},
            "required": ["query"]},
        "run": do_search,
    },
    "kb_get": {
        "description": "按路径取一条知识库条目的完整 Markdown 内容。",
        "inputSchema": {"type": "object", "properties": {
            "path": {"type": "string", "description": "条目相对路径，如 douyin/7690890624584731930.md"}},
            "required": ["path"]},
        "run": do_get,
    },
    "kb_list": {
        "description": "列出知识库条目（可按来源过滤），按入库时间倒序。",
        "inputSchema": {"type": "object", "properties": {
            "type": {"type": "string", "description": "可选，来源过滤"}}},
        "run": do_list,
    },
    "kb_stats": {
        "description": "知识库统计：总数与各来源数量。",
        "inputSchema": {"type": "object", "properties": {}},
        "run": do_stats,
    },
}


def handle(req):
    method = req.get("method")
    _id = req.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": _id, "result": {
            "protocolVersion": PROTOCOL,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "kb-mcp", "version": "1.0.0"}}}
    if method == "notifications/initialized" or method is None:
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": _id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": _id, "result": {"tools": [
            {"name": n, "description": t["description"], "inputSchema": t["inputSchema"]}
            for n, t in TOOLS.items()]}}
    if method == "tools/call":
        name = req["params"]["name"]
        args = req["params"].get("arguments") or {}
        tool = TOOLS.get(name)
        if not tool:
            return {"jsonrpc": "2.0", "id": _id, "error": {"code": -32602, "message": "unknown tool: %s" % name}}
        try:
            result = tool["run"](args)
            return {"jsonrpc": "2.0", "id": _id, "result": {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=1)}]}}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": _id, "result": {
                "content": [{"type": "text", "text": "错误: %s" % e}], "isError": True}}
    if _id is not None:
        return {"jsonrpc": "2.0", "id": _id, "error": {"code": -32601, "message": "unknown method: %s" % method}}
    return None


def serve_stdio():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue
        resp = handle(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


def cli():
    cmd = sys.argv[2] if len(sys.argv) > 2 else ""
    args = sys.argv[3:]
    if cmd == "search":
        a = {"query": args[0] if args else ""}
        for x in args[1:]:
            if x == "--type":
                a["type"] = args[args.index(x) + 1]
            if x == "--limit":
                a["limit"] = args[args.index(x) + 1]
        print(json.dumps(do_search(a), ensure_ascii=False, indent=1))
    elif cmd == "get":
        print(json.dumps(do_get({"path": args[0]}), ensure_ascii=False, indent=1))
    elif cmd == "list":
        print(json.dumps(do_list({"type": args[args.index("--type") + 1] if "--type" in args else None}),
                         ensure_ascii=False, indent=1))
    elif cmd == "stats":
        print(json.dumps(do_stats({}), ensure_ascii=False, indent=1))
    else:
        print(__doc__)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        cli()
    else:
        serve_stdio()
