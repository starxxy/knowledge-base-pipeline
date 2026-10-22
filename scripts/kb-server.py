# -*- coding: utf-8 -*-
"""知识库网页版服务器：静态文件 + 登录验证（中文界面）。

用法:
  python kb-server.py --root "E:\\deepseek\\knowledge-base" --port 8899 [--host 0.0.0.0]

账号文件（默认 <root>/../kb-users.json 或 --users 指定）：
  {"secret": "...", "users": {"stary": {"name": "stary", "salt": "<hex>", "hash": "<hex>"}}}

生成/重置密码:
  python kb-server.py --root ... --set-password stary 新密码
"""
import argparse
import base64
import hashlib
import hmac
import http.cookies
import json
import os
import re
import secrets
import socket
import sys
import time
import urllib.parse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SESSION_TTL = 30 * 24 * 3600  # 30 天
ITER = 200_000
KB_SUBS = ("douyin", "bili", "wechat", "xhs", "notes")


# ---------------------------------------------------------------- 知识库 API
def kb_entries(root):
    import datetime
    out = []
    for sub in KB_SUBS:
        d = Path(root) / sub
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.md")):
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
            out.append({
                "path": p.relative_to(root).as_posix(),
                "title": title,
                "type": meta.get("类型", sub),
                "date": meta.get("入库时间", ""),
                "source": meta.get("原链接", ""),
                "author": meta.get("作者", "") or meta.get("公众号名称", ""),
                "tags": tags,
                "body": body,
            })
    return sorted(out, key=lambda e: e.get("date") or "", reverse=True)


def api_search(root, qs):
    q = (qs.get("q", [""])[0] or "").strip()
    t = (qs.get("type", [""])[0] or "").strip() or None
    limit = min(int(qs.get("limit", ["10"])[0] or 10), 50)
    res = []
    for e in kb_entries(root):
        hay = (e["title"] + " " + " ".join(e["tags"]) + " " + e["body"]).lower()
        if (not q or q.lower() in hay) and (not t or t in e["type"]):
            low, ql = e["body"].lower(), q.lower()
            i = low.find(ql) if ql else 0
            snip = e["body"][max(0, i - 40): i + 200] if i >= 0 else e["body"][:200]
            res.append({k: e[k] for k in ("path", "title", "type", "date", "tags", "author")})
            res[-1]["snippet"] = re.sub(r"\s+", " ", snip).strip()
            if len(res) >= limit:
                break
    return {"count": len(res), "results": res}


def api_entry(root, qs):
    key = (qs.get("id", [""])[0] or "").strip()
    if not key:
        return {"error": "缺少 id 参数"}
    p = (Path(root) / key).resolve()
    if Path(root).resolve() not in p.parents:
        return {"error": "路径越界"}
    if not p.exists():
        for e in kb_entries(root):
            if e["path"].endswith(key) or Path(e["path"]).stem == key:
                p = Path(root) / e["path"]
                break
    if not p.exists():
        return {"error": "条目不存在: %s" % key}
    raw = p.read_text(encoding="utf-8-sig", errors="ignore")
    meta = {}
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", raw, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        raw = m.group(2)
    return {"path": p.relative_to(root).as_posix(), "meta": meta, "content": raw.strip()}


# ---------------------------------------------------------------- 账号管理
def hash_pw(pw, salt_hex):
    salt = bytes.fromhex(salt_hex)
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, ITER).hex()


def load_accounts(path):
    if not path.exists():
        return {"secret": secrets.token_hex(32), "users": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("secret", secrets.token_hex(32))
    data.setdefault("users", {})
    return data


def save_accounts(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass


def set_password(path, user, pw):
    data = load_accounts(path)
    salt = secrets.token_hex(16)
    data["users"][user] = {"name": user, "salt": salt, "hash": hash_pw(pw, salt)}
    save_accounts(path, data)
    print("已设置账号: %s" % user)


# ---------------------------------------------------------------- 会话签名
def sign(secret, payload):
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
    mac = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()[:32]
    return body + "." + mac


def verify(secret, token):
    if not token or "." not in token:
        return None
    body, mac = token.rsplit(".", 1)
    expect = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(mac, expect):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(body.encode()))
    except Exception:
        return None
    if data.get("exp", 0) < time.time():
        return None
    return data


LOGIN_HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>登录 · 我的知识库</title>
<style>
:root{--ink:#1f2329;--muted:#8a9099;--line:#e6e8eb;--accent:#2f6fed;--soft:#f7f8fa}
*{box-sizing:border-box}
body{margin:0;height:100vh;display:flex;align-items:center;justify-content:center;
 font:15px/1.6 -apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
 background:var(--soft);color:var(--ink)}
.card{width:340px;background:#fff;border:1px solid var(--line);border-radius:12px;padding:28px 26px;
 box-shadow:0 1px 3px rgba(15,23,42,.06),0 16px 40px -20px rgba(15,23,42,.2)}
.mark{width:34px;height:34px;border-radius:9px;background:linear-gradient(135deg,var(--accent),#7c5cff);
 color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;margin-bottom:14px}
h1{font-size:18px;margin:0 0 4px}
p.sub{color:var(--muted);font-size:13px;margin:0 0 20px}
label{display:block;font-size:13px;color:#4a5058;margin:12px 0 5px}
input{width:100%;padding:9px 11px;border:1px solid var(--line);border-radius:8px;font-size:14px;outline:none}
input:focus{border-color:var(--accent);box-shadow:0 0 0 3px #eef3fe}
button{width:100%;margin-top:20px;padding:10px;border:0;border-radius:8px;background:var(--accent);
 color:#fff;font-size:14px;font-weight:600;cursor:pointer}
button:hover{filter:brightness(1.05)}
.err{margin-top:14px;color:#c0392b;font-size:13px}
</style></head>
<body><form class="card" method="post" action="/login">
 <div class="mark">知</div>
 <h1>登录知识库</h1>
 <p class="sub">请输入账号密码后继续</p>
 <input type="hidden" name="next" value="__NEXT__">
 <label>用户名</label><input name="u" autocomplete="username" required autofocus>
 <label>密码</label><input name="p" type="password" autocomplete="current-password" required>
 <button type="submit">登 录</button>
 __ERR__
</form></body></html>"""


ROOT = "."  # main() 启动时设置成实际目录


class Handler(SimpleHTTPRequestHandler):
    server_version = "kb-server"

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    # ---------------- 工具 ----------------
    def send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def redirect(self, to, cookie=None):
        self.send_response(302)
        self.send_header("Location", to)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def html(self, text, code=200, cookie=None):
        body = text.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def session_user(self):
        raw = self.headers.get("Cookie", "")
        c = http.cookies.SimpleCookie()
        try:
            c.load(raw)
        except Exception:
            return None
        tok = c.get("kb_session")
        if not tok:
            return None
        data = verify(self.server.accounts["secret"], tok.value)
        return (data or {}).get("u")

    # ---------------- 路由 ----------------
    def api_authed(self):
        u = self.session_user()
        if u:
            return u
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            tok = auth[7:].strip()
            expect = self.server.accounts.get("api_token", "")
            if expect and hmac.compare_digest(tok, expect):
                return "api"
        return None

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if path == "/api/stats":
            if not self.api_authed():
                return self.send_json({"error": "unauthorized"}, 401)
            es = kb_entries(self.server.root)
            by_type = {}
            for e in es:
                by_type[e["type"]] = by_type.get(e["type"], 0) + 1
            return self.send_json({"total": len(es), "by_type": by_type})
        if path == "/api/search":
            if not self.api_authed():
                return self.send_json({"error": "unauthorized"}, 401)
            return self.send_json(api_search(self.server.root, qs))
        if path == "/api/entry":
            if not self.api_authed():
                return self.send_json({"error": "unauthorized"}, 401)
            return self.send_json(api_entry(self.server.root, qs))
        if path == "/login":
            return self.html(LOGIN_HTML.replace("__NEXT__", "").replace("__ERR__", ""))
        if path == "/api/me":
            u = self.session_user()
            return self.send_json({"user": u}, 200 if u else 401)
        if path == "/logout":
            return self.redirect("/login", cookie="kb_session=; Path=/; Max-Age=0")
        if not self.session_user():
            nxt = urllib.parse.quote(self.path)
            return self.redirect("/login?next=" + nxt)
        return super().do_GET()

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/logout":
            return self.send_json({"ok": True}, 200)
        if path != "/login":
            return self.send_json({"error": "not found"}, 404)

        length = int(self.headers.get("Content-Length", 0))
        form = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8", "ignore"))
        user = (form.get("u") or [""])[0].strip()
        pw = (form.get("p") or [""])[0]
        nxt = (form.get("next") or ["/"])[0] or "/"
        rec = self.server.accounts["users"].get(user)
        if rec and hmac.compare_digest(hash_pw(pw, rec["salt"]), rec["hash"]):
            tok = sign(self.server.accounts["secret"], {"u": user, "exp": time.time() + SESSION_TTL})
            cookie = "kb_session=%s; Path=/; Max-Age=%d; HttpOnly; SameSite=Lax" % (tok, SESSION_TTL)
            return self.redirect(nxt, cookie=cookie)
        return self.html(LOGIN_HTML.replace("__NEXT__", nxt).replace("__ERR__", '<div class="err">用户名或密码不对</div>'), code=401)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--port", type=int, default=8899)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--users", default="")
    ap.add_argument("--set-password", nargs=2, metavar=("USER", "PASSWORD"))
    ap.add_argument("--show-token", action="store_true", help="显示 HTTP API 的 Bearer token")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    users_path = Path(args.users) if args.users else Path(__file__).resolve().parent / "kb-users.json"

    accounts = load_accounts(users_path)
    if not users_path.exists():
        save_accounts(users_path, accounts)
    if "api_token" not in accounts:
        accounts["api_token"] = secrets.token_hex(16)
        save_accounts(users_path, accounts)
    if args.show_token:
        print(accounts["api_token"])
        return
    if args.set_password:
        set_password(users_path, args.set_password[0], args.set_password[1])
        return
    if not accounts["users"]:
        print("提示：还没有任何用户（网页登录不可用）；API 的 Bearer token 仍可用。")

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    httpd.root = root
    httpd.accounts = accounts
    global ROOT
    ROOT = str(root)
    print("知识库服务已启动: http://%s:%d/  (根目录 %s)" % (
        socket.gethostbyname(socket.gethostname()), args.port, root))
    httpd.serve_forever()


if __name__ == "__main__":
    main()
