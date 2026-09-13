"""
NOVA - Browser Automation Engine (Chrome DevTools Protocol, stdlib only)
Launches a local Edge/Chrome instance with a loopback-only debug port and
drives it over a raw WebSocket (RFC 6455). No browser-testing dependency.

Every loaded web page is UNTRUSTED input: the data we read back must never
be able to authorize a privileged action on its own.
"""

import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import urllib.request
from typing import Any, Optional

from utils.logger import log


class BrowserUnavailable(Exception):
    """Raised when the browser/CDP connection cannot be established or fails."""


def _xor_mask(payload: bytes, mask: bytes) -> bytes:
    return bytes(b ^ mask[i % 4] for i, b in enumerate(payload))


class CDPClient:
    """Minimal WebSocket client speaking the CDP JSON framing."""

    def __init__(self):
        self._sock: Optional[socket.socket] = None
        self._buf = b""
        self._next_id = 1

    def connect(self, ws_url: str) -> None:
        _, rest = ws_url.split("://", 1)
        hostport, path = rest.split("/", 1)
        host, _, port_s = hostport.partition(":")
        port = int(port_s or 80)
        self._sock = socket.create_connection((host, port), timeout=10)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (
            f"GET /{path} HTTP/1.1\r\n"
            f"Host: {hostport}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self._sock.sendall(req.encode("ascii"))
        headers = b""
        while b"\r\n\r\n" not in headers:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise BrowserUnavailable("CDP handshake failed (no response)")
            headers += chunk
        if b" 101 " not in headers.split(b"\r\n", 1)[0]:
            raise BrowserUnavailable("CDP handshake rejected: %r" % headers[:120])

    # ------------------------------------------------------------- frames
    def _send_frame(self, opcode: int, payload: bytes) -> None:
        if not self._sock:
            raise BrowserUnavailable("CDP not connected")
        b1 = 0x80 | opcode
        mask = os.urandom(4)
        n = len(payload)
        header = bytearray([b1])
        if n < 126:
            header.append(0x80 | n)
        elif n < 65536:
            header.append(0x80 | 126)
            header += struct.pack(">H", n)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", n)
        header += mask
        self._sock.sendall(bytes(header) + _xor_mask(payload, mask))

    def _recv_exact(self, n: int) -> bytes:
        while len(self._buf) < n:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise BrowserUnavailable("CDP connection closed")
            self._buf += chunk
        out, self._buf = self._buf[:n], self._buf[n:]
        return out

    def _recv_frame(self) -> bytes:
        while True:
            b1, b2 = self._recv_exact(2)
            opcode = b1 & 0x0F
            length = b2 & 0x7F
            if length == 126:
                length = struct.unpack(">H", self._recv_exact(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._recv_exact(8))[0]
            mask = self._recv_exact(4) if (b2 & 0x80) else None
            payload = self._recv_exact(length)
            if mask:
                payload = _xor_mask(payload, mask)
            if opcode == 9:      # ping -> pong
                self._send_frame(0xA, payload)
                continue
            if opcode == 8:      # close
                raise BrowserUnavailable("CDP closed the connection")
            if opcode in (1, 2):
                return payload

    def call(self, method: str, params: Optional[dict] = None,
             timeout: float = 30.0) -> dict:
        msg_id = self._next_id
        self._next_id += 1
        payload = json.dumps({"id": msg_id, "method": method,
                              "params": params or {}}).encode("utf-8")
        self._send_frame(0x1, payload)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                data = json.loads(self._recv_frame())
            except (ValueError, BrowserUnavailable):
                break
            if data.get("id") == msg_id:
                if "error" in data:
                    raise BrowserUnavailable(
                        f"CDP error for {method}: {data['error']}")
                return data.get("result", {})
        raise BrowserUnavailable(f"CDP timeout waiting for {method}")

    def evaluate(self, expression: str, timeout: float = 30.0):
        result = self.call("Runtime.evaluate",
                           {"expression": expression, "returnByValue": True,
                            "awaitPromise": True}, timeout=timeout)
        if "exceptionDetails" in result:
            raise BrowserUnavailable(
                "page error: %s" % result["exceptionDetails"][:200])
        return result.get("result", {}).get("value")

    def close(self) -> None:
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None


class BrowserController:
    """Owns one local browser instance and a single page target."""

    def __init__(self, channel: str = "edge", headless: bool = False,
                 port: int = 9223, user_data_dir: str = ""):
        self.channel = channel
        self.headless = headless
        self.port = port
        self.user_data_dir = user_data_dir
        self._proc: Optional[subprocess.Popen] = None
        self.client: Optional[CDPClient] = None
        self._tmp_dir: Optional[str] = None
        self._closed = False

    # -------------------------------------------------------------- launch
    def _find_binary(self) -> str:
        candidates: list[str] = []
        local = os.environ.get("LOCALAPPDATA", "") or os.environ.get("APPDATA", "")
        pf86 = "C:\\Program Files (x86)"
        pf = "C:\\Program Files"
        edge = [os.path.join(pf86, "Microsoft\\Edge\\Application\\msedge.exe"),
                os.path.join(pf, "Microsoft\\Edge\\Application\\msedge.exe")]
        chrome = [os.path.join(pf86, "Google\\Chrome\\Application\\chrome.exe"),
                  os.path.join(pf, "Google\\Chrome\\Application\\chrome.exe"),
                  os.path.join(local, "Google\\Chrome\\Application\\chrome.exe")]
        if self.channel == "chrome":
            candidates = chrome + [shutil.which("chrome") or ""]
        elif self.channel == "auto":
            candidates = edge + chrome + [shutil.which("chrome") or ""]
        else:
            candidates = edge + [shutil.which("msedge") or ""]
        for c in candidates:
            if c and os.path.isfile(c):
                return c
        raise BrowserUnavailable(
            "Could not find Edge or Chrome on this system.")

    def _http_get(self, path: str, timeout: float = 15.0) -> str:
        url = f"http://127.0.0.1:{self.port}{path}"
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.read().decode("utf-8", "replace")

    def _wait_for(self, path: str, timeout: float = 30.0) -> str:
        deadline = time.monotonic() + timeout
        last: Optional[Exception] = None
        while time.monotonic() < deadline:
            try:
                return self._http_get(path, timeout=2.0)
            except Exception as exc:  # server not up yet
                last = exc
                time.sleep(0.3)
        raise BrowserUnavailable(
            f"CDP endpoint on port {self.port} never became ready ({last})")

    def start(self) -> CDPClient:
        """Launch (once) and return a connected CDP client."""
        if self.client is not None:
            return self.client
        binary = self._find_binary()
        self._tmp_dir = self.user_data_dir or tempfile.mkdtemp(prefix="nova_browser_")
        cmd = [binary,
               f"--remote-debugging-port={self.port}",
               f"--user-data-dir={self._tmp_dir}",
               "--no-first-run", "--no-default-browser-check",
               "--remote-allow-origins=*",
               "--disable-popup-blocking"]
        if self.headless:
            cmd.append("--headless=new")
        cmd.append("about:blank")
        log.info("Launching browser: %s (port %d, headless=%s)",
                 os.path.basename(binary), self.port, self.headless)
        self._proc = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            self._wait_for("/json/version")
            pages = json.loads(self._wait_for("/json/list"))
            target = next((p for p in pages if p.get("type") == "page"), None)
            if target is None:
                created = json.loads(urllib.request.urlopen(
                    f"http://127.0.0.1:{self.port}/json/new?about:blank",
                    timeout=10).read())
                target = created
            client = CDPClient()
            client.connect(target["webSocketDebuggerUrl"])
            client.call("Page.enable")
            client.call("Runtime.enable")
            self.client = client
            return client
        except Exception:
            self.stop()
            raise

    @property
    def active(self) -> bool:
        return self.client is not None

    def stop(self) -> None:
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
            self.client = None
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass
            try:
                self._proc.wait(timeout=8)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None
        if self._tmp_dir and not self.user_data_dir:
            try:
                shutil.rmtree(self._tmp_dir, ignore_errors=True)
            except Exception:
                pass
            self._tmp_dir = None

    # ------------------------------------------------------------- driving
    def navigate(self, url: str, timeout: float = 30.0) -> str:
        client = self.start()
        if not url.lower().startswith(("http://", "https://")):
            url = "https://" + url
        client.call("Page.navigate", {"url": url})
        self._wait_ready(timeout)
        return self.visible_text()

    def _wait_ready(self, timeout: float = 30.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if self.client.evaluate("document.readyState") == "complete":
                    return
            except BrowserUnavailable:
                return
            time.sleep(0.3)

    def visible_text(self, limit: int = 2000) -> str:
        client = self.start()
        text = client.evaluate(
            "(() => { const b = document.body; if (!b) return '';"
            " const t = (b.innerText || '').trim();"
            " return t.slice(0, 6000); })()") or ""
        if not text:
            raise BrowserUnavailable("The page has no readable text yet.")
        if len(text) > limit:
            text = text[:limit] + " …"
        return text

    def click_text(self, text: str) -> bool:
        """Click the first element whose text matches (loopback-driven,
        still routed through confirmation because it mutates web state)."""
        client = self.start()
        click = text.replace("\\", "\\\\").replace("'", "\\'")
        expr = (
            "(() => { const q = Array.from(document.querySelectorAll('a,button,"
            "[role=button],input[type=submit]'));"
            f" const el = q.find(e => (e.innerText||'').trim() === '{click}'"
            f" || (e.getAttribute('value')||'') === '{click}');"
            " if (!el) return false; el.click(); return true; })()")
        return bool(client.evaluate(expr))

    def click_selector(self, selector: str) -> bool:
        client = self.start()
        sel = selector.replace("\\", "\\\\").replace("'", "\\'")
        expr = (f"(() => {{ const el = document.querySelector('{sel}');"
                " if (!el) return false; el.click(); return true; })()")
        return bool(client.evaluate(expr))

    def type_text(self, text: str, submit: bool = True) -> bool:
        """Type into the currently focused input (or the first one)."""
        client = self.start()
        safe = json.dumps(text)
        expr = (
            "(() => { const el = document.activeElement && "
            "document.activeElement.tagName === 'INPUT' ? document.activeElement"
            " : document.querySelector('input[type=text],input[type=search],"
            "input:not([type]),textarea'); if (!el) return false;"
            " el.focus(); el.value = " + safe + ";"
            " el.dispatchEvent(new Event('input', {bubbles:true}));"
            " el.dispatchEvent(new Event('change', {bubbles:true}));"
            f" {'el.form ? el.form.requestSubmit() : document.activeElement.blur();' if submit else ''}"
            " return true; })()")
        try:
            return bool(client.evaluate(expr))
        except BrowserUnavailable:
            # form submit may navigate; that is fine, treat as success
            return True

    def scroll(self, direction: str = "down", amount: int = 900) -> str:
        client = self.start()
        if direction == "bottom":
            expr = "window.scrollTo(0, document.body.scrollHeight); 'bottom'"
        elif direction == "up":
            expr = f"window.scrollBy(0, -{amount}); 'up'"
        else:
            expr = f"window.scrollBy(0, {amount}); 'down'"
        try:
            return str(client.evaluate(expr) or "down")
        except BrowserUnavailable:
            return direction


# Shared single browser instance used by the tool layer.
_browser: Optional[BrowserController] = None


def get_browser() -> BrowserController:
    global _browser
    if _browser is None:
        from config import config
        if not config.browser.enabled:
            raise BrowserUnavailable("Browser automation is disabled.")
        _browser = BrowserController(
            channel=config.browser.channel,
            headless=config.browser.headless,
            port=config.browser.port,
            user_data_dir=config.browser.user_data_dir,
        )
    return _browser


def close_browser() -> None:
    global _browser
    if _browser is not None:
        _browser.stop()
        _browser = None