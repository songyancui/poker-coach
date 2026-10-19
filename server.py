#!/usr/bin/env python3
"""电脑版本地服务：提供 index.html，并把 /api/ask 的提问流式转发给 DeepSeek。
（手机 App 不需要这个服务：在 App 设置里填密钥即可直连。电脑网页也可以直接在设置里填密钥。）
密钥读取顺序：环境变量 DEEPSEEK_API_KEY，其次同目录下的 deepseek_key.txt（只放一行密钥）。
用法：python3 server.py  然后打开 http://localhost:8765/
"""
import json, os, sys, urllib.request, urllib.error
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", "8765"))
API = "https://api.deepseek.com/chat/completions"
ALLOWED_MODELS = {"deepseek-flash", "deepseek-v4-pro"}


def load_key():
    k = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if k:
        return k
    try:
        with open(os.path.join(HERE, "deepseek_key.txt")) as f:
            return f.read().strip()
    except OSError:
        return ""


class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=HERE, **kw)

    def end_headers(self):
        # 开发时每次都取最新页面，避免浏览器缓存旧版
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == "/api/status":
            return self._json(200, {"hasKey": bool(load_key()), "provider": "deepseek"})
        super().do_GET()

    def do_POST(self):
        if self.path != "/api/ask":
            return self._json(404, {"error": "not found"})
        key = load_key()
        if not key:
            return self._json(400, {"error": "没有找到 DeepSeek 密钥。请在页面设置里填写，或设置环境变量 DEEPSEEK_API_KEY，或在 server.py 同目录新建 deepseek_key.txt（只写一行密钥）后重启服务。"})
        try:
            n = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(n) or b"{}")
            model = body.get("model", "deepseek-flash")
            if model not in ALLOWED_MODELS:
                model = "deepseek-flash"
            thinking = body.get("thinking", {"type": "disabled"})
            payload = {
                "model": model,
                "messages": body.get("messages", [])[-14:],
                "stream": True,
                "max_tokens": min(int(body.get("max_tokens", 1200)), 4000),
                "thinking": {"type": "enabled" if thinking.get("type") == "enabled" else "disabled"},
            }
        except Exception as e:
            return self._json(400, {"error": f"请求格式错误：{e}"})
        req = urllib.request.Request(
            API,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        )
        try:
            resp = urllib.request.urlopen(req, timeout=120)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:500]
            return self._json(e.code, {"error": f"DeepSeek 返回 {e.code}：{detail}"})
        except Exception as e:
            return self._json(502, {"error": f"连不上 DeepSeek：{e}"})
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.end_headers()
        try:
            while True:
                line = resp.readline()
                if not line:
                    break
                self.wfile.write(line)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            resp.close()

    def log_message(self, fmt, *args):
        if "/api/" in (args[0] if args else ""):
            sys.stderr.write("[api] " + fmt % args + "\n")


if __name__ == "__main__":
    print(f"serving http://localhost:{PORT}/  provider=deepseek  key={'OK' if load_key() else '未设置'}")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
