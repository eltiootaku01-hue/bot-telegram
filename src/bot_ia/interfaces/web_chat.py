"""Lightweight browser chat surface for BOT-IA.

No frontend build, Node runtime, database, or extra dependency is required.
The browser stores its own visible chat history; BOT-IA remains the source of
truth for the configured local library and persistent runtime state.
"""

from __future__ import annotations

import hmac
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from bot_ia.core.application import ApplicationRequest, BotApplication
from .web import MAX_MESSAGE_CHARS, MAX_ID_CHARS, WebApi, WebApiError, ExternalApiAuthorizationError


CHAT_HTML = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#111827">
<title>BOT-IA</title>
<style>
:root{color-scheme:dark;font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#111827;color:#f3f4f6}
*{box-sizing:border-box}body{margin:0;min-height:100vh;background:#111827}
.app{max-width:900px;margin:auto;min-height:100vh;display:flex;flex-direction:column}
header{padding:14px 16px;border-bottom:1px solid #374151;display:flex;gap:10px;align-items:center;justify-content:space-between;position:sticky;top:0;background:#111827ee;backdrop-filter:blur(8px);z-index:2}
.title{font-weight:800}.sub{font-size:12px;color:#9ca3af}.settings{display:flex;gap:6px;align-items:center}
input,textarea,button{font:inherit}input{width:240px;max-width:48vw;background:#1f2937;border:1px solid #4b5563;color:#f3f4f6;border-radius:8px;padding:7px 9px}
main{flex:1;padding:16px;display:flex;flex-direction:column;gap:12px}.messages{display:flex;flex-direction:column;gap:10px;padding-bottom:110px}
.msg{max-width:85%;padding:11px 13px;border-radius:14px;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.45}.user{align-self:flex-end;background:#2563eb}.bot{align-self:flex-start;background:#1f2937;border:1px solid #374151}.meta{font-size:11px;color:#9ca3af;margin-top:5px}
.composer{position:sticky;bottom:0;padding:10px 0 calc(10px + env(safe-area-inset-bottom));background:#111827f5;backdrop-filter:blur(8px)}
.row{display:flex;gap:8px}textarea{flex:1;min-height:52px;max-height:180px;resize:vertical;background:#1f2937;border:1px solid #4b5563;color:#f3f4f6;border-radius:12px;padding:10px 12px}button{border:0;border-radius:10px;padding:10px 14px;background:#2563eb;color:white;font-weight:700;cursor:pointer}button:disabled{opacity:.55;cursor:wait}
.note{font-size:11px;color:#9ca3af;padding-top:6px}.danger{color:#fca5a5}
@media(max-width:600px){header{align-items:flex-start;flex-direction:column}.settings{width:100%}.settings input{flex:1;max-width:none}.msg{max-width:94%}}
</style></head>
<body><div class="app">
<header><div><div class="title">🤖 BOT-IA</div><div class="sub">Chat local · biblioteca y memoria del proyecto</div></div>
<div class="settings"><input id="token" type="password" placeholder="Token (solo si está protegido)" autocomplete="off"><button id="clear" type="button">Limpiar</button></div></header>
<main><section id="messages" class="messages"></section><div class="composer"><div class="row"><textarea id="input" placeholder="Escribe un mensaje…" autofocus></textarea><button id="send">Enviar</button></div><div id="status" class="note">Conectado a este BOT-IA.</div></div></main>
</div>
<script>
const messages=document.getElementById('messages'), input=document.getElementById('input'), send=document.getElementById('send'), status=document.getElementById('status'), token=document.getElementById('token');
const KEY='bot-ia-chat-v1', TOKEN='bot-ia-token-v1';
let history=JSON.parse(localStorage.getItem(KEY)||'[]'); token.value=sessionStorage.getItem(TOKEN)||'';
function save(){localStorage.setItem(KEY,JSON.stringify(history.slice(-80)));}
function render(){messages.innerHTML=''; for(const m of history){const box=document.createElement('div');box.className='msg '+(m.role==='user'?'user':'bot');box.textContent=m.text;messages.appendChild(box);} window.scrollTo(0,document.body.scrollHeight);}
function add(role,text){history.push({role,text});save();render();}
async function ask(){const text=input.value.trim();if(!text||send.disabled)return; input.value='';add('user',text);send.disabled=true;status.textContent='Procesando…';
try{const headers={'Content-Type':'application/json'};const t=token.value.trim();if(t){headers.Authorization='Bearer '+t;sessionStorage.setItem(TOKEN,t)}
const r=await fetch('/v1/query',{method:'POST',headers,body:JSON.stringify({message:text,user_id:'web-user',conversation_id:'web-session'})});
const data=await r.json().catch(()=>({error:'Respuesta no válida'})); if(!r.ok) throw new Error(data.error||('HTTP '+r.status)); add('assistant',data.answer||'Sin respuesta.'); status.textContent='Ruta: '+(data.route||'desconocida')+(data.provider?' · '+data.provider:'');
}catch(e){add('assistant','No pude completar la consulta: '+e.message);status.textContent='Error de conexión o autorización.';}
finally{send.disabled=false;input.focus();}}
send.onclick=ask;input.addEventListener('keydown',e=>{if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)){e.preventDefault();ask()}});document.getElementById('clear').onclick=()=>{history=[];save();render()};render();
</script></body></html>"""


def run_web_chat_server(
    application: BotApplication,
    *,
    host: str = "127.0.0.1",
    port: int = 8787,
    api_token: str | None = None,
    allow_external_api: bool = False,
) -> None:
    api = WebApi(application, api_token=api_token, allow_external_api=allow_external_api)

    class Handler(BaseHTTPRequestHandler):
        server_version = "BOT-IA-WebChat/1.0"

        def _send(self, status: int, payload: object, content_type: str = "application/json") -> None:
            if content_type == "text/html":
                body = payload.encode("utf-8") if isinstance(payload, str) else bytes(payload)
            else:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:  # noqa: N802
            self._send(HTTPStatus.NO_CONTENT, b"", "text/plain")

        def do_GET(self) -> None:  # noqa: N802
            if self.path in {"/", "/chat"}:
                self._send(HTTPStatus.OK, CHAT_HTML, "text/html")
                return
            if self.path == "/health":
                self._send(HTTPStatus.OK, {"ok": True, "service": "bot-ia-web-chat"})
                return
            self._send(HTTPStatus.NOT_FOUND, {"error": "not_found"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/v1/query":
                self._send(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            if not api.authorize(self.headers.get("Authorization")):
                self._send(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 1_000_000:
                    raise WebApiError("request body size is invalid")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                result = api.query(payload)
            except ExternalApiAuthorizationError as error:
                self._send(HTTPStatus.FORBIDDEN, {"error": str(error)})
                return
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError, WebApiError) as error:
                self._send(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            except Exception:
                self._send(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error"})
                return
            self._send(HTTPStatus.OK, result)

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"BOT-IA Web Chat escuchando en http://{host}:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
