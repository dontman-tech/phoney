"""Phoney web dashboard — local HTTP UI at http://127.0.0.1:3000/phoney.

Zero dependencies (http.server). Serves a single-page dashboard over the
running daemon: device list, pairing, battery, SMS, media control,
find-my-phone, clipboard push, and file send.
"""
from __future__ import annotations

import html
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger(__name__)

PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Phoney Dashboard</title>
<style>
  :root { color-scheme: dark; }
  body { font-family: system-ui, sans-serif; background:#0c0c0c; color:#d7e2ea;
         margin:0; padding:2rem; max-width: 900px; margin-inline:auto; }
  h1 { font-weight: 800; letter-spacing: -1px; }
  h1 span { color:#b600a8; }
  .card { background:#141414; border:1px solid #ffffff14; border-radius:14px;
          padding:1rem 1.25rem; margin: .75rem 0; }
  .row { display:flex; gap:.6rem; align-items:center; flex-wrap:wrap; }
  button, .btn { background:#b600a8; color:#fff; border:0; border-radius:999px;
          padding:.5rem 1.1rem; font: inherit; cursor:pointer; }
  button.alt { background:#2a2a2a; }
  input, select { background:#0c0c0c; color:inherit; border:1px solid #ffffff2a;
          border-radius:8px; padding:.45rem .7rem; font:inherit; }
  .muted { color:#8fa3b0; font-size:.85rem; }
  .paired { color:#4cd964; } .unpaired { color:#ff9500; }
  #log { font-family: ui-monospace, monospace; font-size:.8rem; color:#8fa3b0;
         white-space: pre-wrap; }
  a { color:#b600a8; }
</style></head>
<body>
<h1>Phoney <span>dashboard</span></h1>
<p class="muted">Phone Link for Linux — local only, nothing leaves 127.0.0.1.</p>

<div class="card">
  <div class="row"><strong>Devices</strong>
    <button onclick="api('refresh')">Rescan</button></div>
  <div id="devices" class="row" style="margin-top:.6rem"></div>
</div>

<div class="card">
  <div class="row"><strong>Phone actions</strong>
    <select id="target"></select></div>
  <div class="row" style="margin-top:.6rem">
    <button onclick="api('battery')">Battery</button>
    <button onclick="api('ring')">Ring phone</button>
    <button onclick="api('media', {cmd:'PlayPause'})">Play/Pause</button>
    <button onclick="api('media', {cmd:'Next'})">Next</button>
    <button onclick="api('mute')">Mute call</button>
    <button onclick="api('clipboard')">Push clipboard</button>
  </div>
  <div class="row" style="margin-top:.6rem">
    <input id="smsnum" placeholder="+237…" style="width:9rem">
    <input id="smstext" placeholder="SMS text">
    <button onclick="api('sms')">Send SMS</button>
  </div>
</div>

<div class="card">
  <strong>Events</strong><div id="log" style="margin-top:.5rem"></div>
</div>

<script>
const $ = (id) => document.getElementById(id);
async function api(action, body = {}) {
  const r = await fetch('/api', { method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ action, ...body, target: $('target').value }) });
  const data = await r.json();
  log(JSON.stringify(data));
  if (action === 'refresh' || action === 'battery') render(data);
}
function render(data) {
  $('devices').innerHTML = (data.devices || []).map(d =>
    `<span class="card ${d.paired ? 'paired' : 'unpaired'}">
       <strong>${d.name}</strong> <span class="muted">${d.id}</span>
       ${d.paired ? '· paired' : `<button onclick="api('pair', {name:'${d.name}'})">Pair</button>`}
       ${d.battery != null ? ' · 🔋' + d.battery + '%' : ''}
     </span>`).join('') || '<span class="muted">No devices yet — make sure the phone is on the same network.</span>';
  const sel = $('target');
  const cur = sel.value;
  sel.innerHTML = (data.devices || []).map(d => `<option>${d.name}</option>`).join('');
  if (cur && (data.devices || []).some(d => d.name === cur)) sel.value = cur;
}
function log(line) { $('log').textContent = line + "\\n" + $('log').textContent.slice(0, 4000); }
render({});
setInterval(() => api('refresh'), 10000);
api('refresh');
</script>
</body></html>
"""


class _Handler(BaseHTTPRequestHandler):
    daemon = None  # injected

    def log_message(self, *a):  # silence default noise
        pass

    def _send(self, code, body: bytes, ctype="text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send(200, PAGE.encode())

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            self._send(400, b'{"error":"bad json"}', "application/json")
            return
        self._send(200, json.dumps(self._dispatch(req)).encode(),
                   "application/json")

    def _dispatch(self, req: dict) -> dict:
        d, action = self.daemon, req.get("action", "")
        target = req.get("target")

        def snap(daemon=d):
            devices = [{
                "name": dev.name, "id": dev.id, "paired": dev.paired,
                "battery": (daemon.battery.get(dev.id) or {}).get("level"),
            } for dev in daemon.devices()]
            return {"devices": devices}

        if action == "refresh":
            d.transport.announce()
            return snap()
        if action == "pair":
            try:
                dev = d.pair(target)
                return {"ok": True, "paired": dev.paired, **snap()}
            except LookupError as e:
                return {"error": str(e), **snap()}
        try:
            dev = d._find(target)
        except LookupError as e:
            return {"error": str(e), **snap()}
        if action == "battery":
            d.battery.refresh(dev)
            return {**snap()}
        if action == "ring":
            d.ring(target); return {"ok": True}
        if action == "media":
            d.media(target, req.get("cmd", "PlayPause")); return {"ok": True}
        if action == "mute":
            d.mute_call(target); return {"ok": True}
        if action == "clipboard":
            d.push_clipboard(target); return {"ok": True}
        if action == "sms":
            d.send_sms(target, req.get("number", ""), req.get("text", ""))
            return {"ok": True}
        return {"error": f"unknown action {action!r}"}

    # expose via a method so handlers can't shadow built-ins
    _dispatch = _dispatch


def serve(daemon, host: str = "127.0.0.1", port: int = 3000) -> ThreadingHTTPServer:
    handler = type("H", (_Handler,), {"daemon": daemon})
    httpd = ThreadingHTTPServer((host, port), handler)
    threading.Thread(target=httpd.serve_forever, name="phoney-dashboard",
                     daemon=True).start()
    log.info("Dashboard on http://%s:%s", host, port)
    return httpd
