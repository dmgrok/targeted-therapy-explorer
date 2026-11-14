#!/usr/bin/env python3
"""WCAG AA contrast gate: every visible text element, in a headless browser.

For a sample of pages (the steps home, the drug-pages start, one biomarker page, one table per biomarker,
the cases index, and every case page, each case page also at 390px), compute the effective foreground and
background colour of every visible text element, accounting for opacity
and inherited backgrounds. The build fails if any pair is below 4.5:1.

This launches the Chromium/Chrome binary available on the machine
(google-chrome locally; the CI workflow installs Chrome).
"""
from __future__ import annotations

import http.server
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
import urllib.request
from base64 import b64encode
from hashlib import sha1
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
THRESHOLD = 4.5

SAMPLE = [
    "index.html",
    "options/index.html",
    "b/EGFR/index.html",
    "b/EGFR/lung-cancer/egfr-exon-19-deletion-or-l858r/as-a-first-treatment.html",
    "b/ALK/lung-cancer/alk-fusion-or-alk-positive/as-a-first-treatment.html",
    "b/BRAF-V600E/melanoma-skin-cancer/braf-v600e/after-surgery.html",
    "b/KRAS-G12C/lung-cancer/kras-g12c/as-a-first-treatment.html",
    "b/HER2/breast-cancer/her2-positive/as-a-first-treatment.html",
    "b/NTRK/solid-tumours-several-cancer-types/ntrk-fusion/label-does-not-say-when-it-is-used.html",
    "b/MSI-H-dMMR/bowel-cancer/msi-h-or-dmmr/as-a-first-treatment.html",
    "cases/index.html",
    "cases/sijbrandij.html",
    "cases/freeman-daily.html",
    "cases/augenstein.html",
    "cases/feldman.html",
    "cases/olson.html",
]
# Pages also checked at a 390px phone width (mobile diagram variants).
MOBILE = ["index.html"] + [p for p in SAMPLE if p.startswith("cases/") and p != "cases/index.html"]

# JS: walk visible text, compose colours, return ratios.
COLLECT_JS = r"""
() => {
  const THRESHOLD = 4.5;

  function parseRGBA(s) {
    if (!s || s === "transparent") return [0,0,0,0];
    const m = s.match(/rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)(?:\s*,\s*([\d.]+))?\s*\)/);
    if (m) return [+m[1], +m[2], +m[3], m[4] === undefined ? 1 : +m[4]];
    return [0,0,0,0];
  }
  function blend(src, dst) {
    const a = src[3];
    if (a <= 0) return dst.slice();
    if (a >= 1) return [src[0], src[1], src[2], 1];
    return [
      src[0]*a + dst[0]*(1-a),
      src[1]*a + dst[1]*(1-a),
      src[2]*a + dst[2]*(1-a),
      1
    ];
  }
  function applyOpacity(color, backdrop, o) {
    if (o >= 1) return color;
    return [
      color[0]*o + backdrop[0]*(1-o),
      color[1]*o + backdrop[1]*(1-o),
      color[2]*o + backdrop[2]*(1-o),
      1
    ];
  }
  function lum(c) {
    const f = (v) => {
      v = v/255;
      return v <= 0.04045 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4);
    };
    return 0.2126*f(c[0]) + 0.7152*f(c[1]) + 0.0722*f(c[2]);
  }
  function contrast(a, b) {
    const L1 = lum(a), L2 = lum(b);
    const hi = Math.max(L1, L2), lo = Math.min(L1, L2);
    return (hi+0.05)/(lo+0.05);
  }
  function hex(c) {
    const r = Math.round(c[0]), g = Math.round(c[1]), b = Math.round(c[2]);
    return "#" + [r,g,b].map(x => x.toString(16).padStart(2,"0")).join("");
  }

  function isHidden(el) {
    let e = el;
    while (e && e.nodeType === 1) {
      const st = getComputedStyle(e);
      if (st.display === "none" || st.visibility === "hidden") return true;
      if (parseFloat(st.opacity) === 0) return true;
      if (e.hidden) return true;
      // Closed details: skip content, keep the summary.
      if (e.tagName === "DETAILS" && !e.open) {
        // el is inside a closed details. Allowed only if it is (in) the summary.
        if (!el.closest("summary")) return true;
      }
      e = e.parentElement;
    }
    return false;
  }

  // Backdrop immediately behind `el` (ancestors only), then el's own bg,
  // then effective text colour, all with opacity groups.
  function effectiveColours(el) {
    const chain = [];
    for (let e = el; e; e = e.parentElement) chain.unshift(e);
    // Default canvas, then html, then the chain (html may appear twice — fine).
    let behind = [255,255,255,1];
    const htmlBg = parseRGBA(getComputedStyle(document.documentElement).backgroundColor);
    if (htmlBg[3] > 0) behind = blend(htmlBg, behind);

    function paintNode(node, backdrop) {
      const st = getComputedStyle(node);
      const o = parseFloat(st.opacity);
      const bg = parseRGBA(st.backgroundColor);
      // Background is painted, then the whole node (bg + content) is
      // composited at `opacity` onto the incoming backdrop.
      let withBg = backdrop;
      if (bg[3] > 0) withBg = blend(bg, backdrop);
      if (o < 1) withBg = applyOpacity(withBg, backdrop, o);
      return { withBg, backdrop, opacity: o, rawBg: bg };
    }

    let backdrop = behind;
    for (let i = 0; i < chain.length - 1; i++) {
      backdrop = paintNode(chain[i], backdrop).withBg;
    }
    const self = paintNode(el, backdrop);
    const st = getComputedStyle(el);
    const fgRaw = parseRGBA(st.color);
    // Text is painted onto the element's background-over-backdrop (before
    // the element's own opacity), then the opacity group is flattened.
    let localBg = backdrop;
    if (self.rawBg[3] > 0) localBg = blend(self.rawBg, backdrop);
    let fg = fgRaw;
    if (fgRaw[3] < 1) fg = blend(fgRaw, localBg);
    const o = self.opacity;
    const fgFinal = o < 1 ? applyOpacity(fg, backdrop, o) : fg;
    const bgFinal = self.withBg;
    return { fg: fgFinal, bg: bgFinal, rawColor: st.color, rawBg: st.backgroundColor, opacity: o };
  }

  const seen = new Set();
  const results = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
  let node;
  while ((node = walker.nextNode())) {
    const text = (node.nodeValue || "").replace(/\s+/g, " ").trim();
    if (!text) continue;
    const el = node.parentElement;
    if (!el) continue;
    const tag = el.tagName;
    if (["SCRIPT","STYLE","NOSCRIPT","TEMPLATE"].includes(tag)) continue;
    if (isHidden(el)) continue;
    const rects = el.getClientRects();
    if (!rects.length) continue;
    let visible = false;
    for (const r of rects) {
      if (r.width >= 1 && r.height >= 1) { visible = true; break; }
    }
    if (!visible) continue;
    let cols = effectiveColours(el);
    // Inline SVG text: the ink is the computed fill, and the solid colour
    // drawn behind it is declared on the <text> as data-bg (diagrams.py).
    if (el instanceof SVGElement) {
      const host = el.closest("[data-bg]");
      const fill = parseRGBA(getComputedStyle(el).fill);
      if (!host || fill[3] === 0) {
        results.push({tag: tag.toLowerCase(), desc: "svg text without data-bg", text: text.slice(0,80),
                      fg: "?", bg: "?", ratio: 0, opacity: 1});
        continue;
      }
      const hb = host.getAttribute("data-bg").replace("#", "");
      const bgc = [parseInt(hb.slice(0,2),16), parseInt(hb.slice(2,4),16), parseInt(hb.slice(4,6),16), 1];
      cols = { fg: blend(fill, bgc), bg: bgc, opacity: 1 };
    }
    const ratio = contrast(cols.fg, cols.bg);
    const key = [tag, el.className, hex(cols.fg), hex(cols.bg), text.slice(0,40)].join("|");
    if (seen.has(key)) continue;
    seen.add(key);
    const desc = (
      (el.id ? "#"+el.id : "") +
      (el.className && typeof el.className === "string" && el.className.trim()
        ? "." + el.className.trim().split(/\s+/).slice(0,3).join(".")
        : "")
    );
    results.push({
      tag: tag.toLowerCase(),
      desc: (tag.toLowerCase() + desc) || tag.toLowerCase(),
      text: text.slice(0, 80),
      fg: hex(cols.fg),
      bg: hex(cols.bg),
      ratio: Math.round(ratio * 100) / 100,
      opacity: cols.opacity,
    });
  }
  results.sort((a,b) => a.ratio - b.ratio);
  return results;
}
"""


def find_chrome() -> str:
    for name in (
        os.environ.get("CHROME_BIN"),
        os.environ.get("CHROMIUM_BIN"),
        shutil.which("google-chrome"),
        shutil.which("google-chrome-stable"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        shutil.which("chrome"),
    ):
        if name and Path(name).is_file():
            return name
    raise SystemExit(
        "FAIL: no Chrome/Chromium binary found for the contrast gate. "
        "Install Chrome or set CHROME_BIN."
    )


class _WS:
    """Minimal WebSocket client for the Chrome DevTools Protocol."""

    def __init__(self, url: str):
        from urllib.parse import urlparse
        u = urlparse(url)
        host, port = u.hostname, u.port or 80
        path = u.path + (("?" + u.query) if u.query else "")
        key = b64encode(os.urandom(16)).decode()
        req = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock = socket.create_connection((host, port), timeout=30)
        self.sock.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise RuntimeError("CDP websocket handshake failed")
            buf += chunk
        self.sock.settimeout(30)
        self._id = 0

    def send(self, payload: bytes) -> None:
        fin, mask_bit = 0x81, 0x80
        n = len(payload)
        mask = os.urandom(4)
        if n < 126:
            header = bytes([fin, mask_bit | n])
        elif n < 65536:
            header = bytes([fin, mask_bit | 126]) + struct.pack("!H", n)
        else:
            header = bytes([fin, mask_bit | 127]) + struct.pack("!Q", n)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(header + mask + masked)

    def recv(self) -> str:
        def read(n: int) -> bytes:
            buf = b""
            while len(buf) < n:
                chunk = self.sock.recv(n - len(buf))
                if not chunk:
                    raise RuntimeError("CDP websocket closed")
                buf += chunk
            return buf

        while True:
            hdr = read(2)
            opcode = hdr[0] & 0x0F
            length = hdr[1] & 0x7F
            masked = bool(hdr[1] & 0x80)
            if length == 126:
                length = struct.unpack("!H", read(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", read(8))[0]
            mask = read(4) if masked else b""
            data = read(length)
            if masked:
                data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
            if opcode == 0x8:  # close
                raise RuntimeError("CDP websocket close")
            if opcode == 0x1:
                return data.decode()
            if opcode == 0x2:
                return data.decode("utf-8", "replace")
            # ping/pong/continuation: ignore pings, loop
            if opcode == 0x9:
                continue

    def call(self, method: str, **params):
        self._id += 1
        mid = self._id
        self.send(json.dumps({"id": mid, "method": method, "params": params}).encode())
        while True:
            msg = json.loads(self.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"CDP {method}: {msg['error']}")
                return msg.get("result") or {}

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _SiteServer(threading.Thread):
    def __init__(self, root: Path, port: int):
        super().__init__(daemon=True)
        self.root = root
        self.port = port
        handler = http.server.SimpleHTTPRequestHandler
        # Serve SITE as the root.
        # Defined inside so the directory is bound.

        class H(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *a, **k):
                super().__init__(*a, directory=str(root), **k)

            def log_message(self, *a):  # noqa: ARG002
                return

        self._httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), H)

    def run(self) -> None:
        self._httpd.serve_forever()

    def stop(self) -> None:
        self._httpd.shutdown()


def _chrome_ready(port: int) -> bool:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1)
        return True
    except Exception:
        return False


def _port_from_devtools_file(profile: Path) -> int | None:
    path = profile / "DevToolsActivePort"
    if not path.is_file():
        return None
    try:
        first = path.read_text().splitlines()[0].strip()
    except OSError:
        return None
    return int(first) if first.isdigit() else None


def _launch_chrome(chrome: str, port: int) -> tuple[subprocess.Popen, int]:
    """Start headless Chrome and return (process, actual DevTools port).

    Newer Chrome sometimes writes a different port to DevToolsActivePort,
    and `--headless=new` has been known not to bind the debug port on
    some CI images. We wait on both the requested port and that file,
    capture logs, and fall back to classic `--headless` if needed.
    """
    profile = Path("/tmp/tte-chrome-contrast")
    log_path = Path("/tmp/tte-chrome-contrast.log")

    def start(headless_flag: str) -> subprocess.Popen:
        if profile.exists():
            shutil.rmtree(profile, ignore_errors=True)
        profile.mkdir(parents=True)
        cmd = [
            chrome,
            headless_flag,
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            f"--remote-debugging-port={port}",
            "--remote-debugging-address=127.0.0.1",
            "--remote-allow-origins=*",
            f"--user-data-dir={profile}",
            "about:blank",
        ]
        log_f = open(log_path, "wb")
        return subprocess.Popen(cmd, stdout=log_f, stderr=subprocess.STDOUT)

    def wait(proc: subprocess.Popen, seconds: float = 20.0) -> int | None:
        deadline = time.time() + seconds
        while time.time() < deadline:
            if proc.poll() is not None:
                return None
            actual = _port_from_devtools_file(profile)
            if actual is not None and _chrome_ready(actual):
                return actual
            if _chrome_ready(port):
                return port
            time.sleep(0.2)
        return None

    def log_tail() -> str:
        try:
            return log_path.read_text(errors="replace")[-4000:]
        except OSError:
            return ""

    flags = ["--headless=new", "--headless"]
    last_proc = None
    for flag in flags:
        if last_proc is not None and last_proc.poll() is None:
            last_proc.terminate()
            try:
                last_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                last_proc.kill()
        proc = start(flag)
        actual = wait(proc)
        if actual is not None:
            return proc, actual
        err = log_tail()
        print(
            f"chrome {flag} did not open DevTools "
            f"(exit={proc.poll()}). log:\n{err}",
            flush=True,
        )
        last_proc = proc
    raise RuntimeError(
        "Chrome DevTools port did not open. "
        f"binary={chrome} log:\n{log_tail()}"
    )


def _connect_page(debug_port: int) -> _WS:
    # Prefer an existing tab from the about:blank launch; /json/new is
    # PUT-only on some Chrome versions and returns 405 on GET.
    with urllib.request.urlopen(f"http://127.0.0.1:{debug_port}/json/list") as r:
        tabs = json.loads(r.read().decode())
    page = None
    for t in tabs:
        if t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
            page = t
            break
    if page is None:
        req = urllib.request.Request(
            f"http://127.0.0.1:{debug_port}/json/new?about:blank",
            method="PUT",
        )
        with urllib.request.urlopen(req) as r:
            page = json.loads(r.read().decode())
    ws = _WS(page["webSocketDebuggerUrl"])
    ws.call("Runtime.enable")
    ws.call("Page.enable")
    return ws


def _measure(ws: _WS, url: str) -> list[dict]:
    ws.call("Page.navigate", url=url)
    # Wait for load.
    deadline = time.time() + 20
    loaded = False
    # Poll readyState.
    while time.time() < deadline:
        res = ws.call("Runtime.evaluate", expression="document.readyState", returnByValue=True)
        if (res.get("result") or {}).get("value") == "complete":
            loaded = True
            break
        time.sleep(0.1)
    if not loaded:
        raise RuntimeError(f"page did not load: {url}")
    # Give webfonts / CSS a beat.
    time.sleep(0.2)
    res = ws.call(
        "Runtime.evaluate",
        expression=f"({COLLECT_JS})()",
        returnByValue=True,
        awaitPromise=False,
    )
    val = (res.get("result") or {}).get("value")
    if not isinstance(val, list):
        raise RuntimeError(f"contrast script returned {res}")
    return val


def main() -> int:
    for rel in SAMPLE:
        if not (SITE / rel).is_file():
            print(f"FAIL: missing sample page site/{rel} — run scripts/build_site.py")
            return 1
    chrome = find_chrome()
    http_port = _free_port()
    debug_port = _free_port()
    server = _SiteServer(SITE, http_port)
    server.start()
    proc = None
    lowest = None
    failures = []
    n_checked = 0
    try:
        print(f"contrast gate using {chrome}", flush=True)
        proc, debug_port = _launch_chrome(chrome, debug_port)
        ws = _connect_page(debug_port)
        runs = [(rel, None) for rel in SAMPLE] + [(rel, 390) for rel in MOBILE]
        for rel, width in runs:
            url = f"http://127.0.0.1:{http_port}/{rel}"
            if width:
                ws.call("Emulation.setDeviceMetricsOverride", width=width, height=844,
                        deviceScaleFactor=1, mobile=True)
            rows = _measure(ws, url)
            if width:
                ws.call("Emulation.clearDeviceMetricsOverride")
                rel = f"{rel} @{width}px"
            if not rows:
                print(f"FAIL: no visible text measured on {rel}")
                return 1
            n_checked += len(rows)
            page_low = rows[0]
            for r in rows:
                r["page"] = rel
                if lowest is None or r["ratio"] < lowest["ratio"]:
                    lowest = r
                if r["ratio"] < THRESHOLD:
                    failures.append(r)
            print(
                f"  {rel}: {len(rows)} text elements, "
                f"lowest {page_low['ratio']:.2f}:1 on {page_low['desc']} "
                f"({page_low['fg']} on {page_low['bg']}) «{page_low['text'][:50]}»"
            )
        ws.close()
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        server.stop()

    if lowest is None:
        print("FAIL: no elements measured")
        return 1
    print(
        f"\nLowest ratio: {lowest['ratio']:.2f}:1 on {lowest['page']} "
        f"{lowest['desc']} — {lowest['fg']} on {lowest['bg']} "
        f"«{lowest['text']}»"
    )
    print(f"Checked {n_checked} visible text elements on {len(SAMPLE)} pages (+ {len(MOBILE)} pages at 390px).")
    if failures:
        print(f"\n{len(failures)} FAIL(S) below {THRESHOLD}:1")
        for r in failures[:25]:
            print(
                f"  {r['ratio']:.2f}:1  {r['page']}  {r['desc']}  "
                f"{r['fg']} on {r['bg']}  «{r['text'][:60]}»"
            )
        if len(failures) > 25:
            print(f"  … and {len(failures)-25} more")
        return 1
    print(f"PASS: every measured element is at least {THRESHOLD}:1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
