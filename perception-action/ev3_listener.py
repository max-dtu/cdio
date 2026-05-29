#!/usr/bin/env python3
"""Ultra-minimal EV3 WebSocket listener.

Supports one client, short text frames (<126 bytes), newline-separated commands.
"""

import argparse, base64, hashlib, logging, os, socket, struct

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)
WS_GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'


def write(path, v):
    try:
        with open(path, 'w') as f:
            f.write(str(v))
    except Exception:
        pass


def find(m):
    d = '/sys/class/tacho-motor'
    if not os.path.isdir(d):
        return None
    p = os.path.join(d, m)
    if os.path.isdir(p):
        return p
    return None


class R:
    def __init__(self, s=50):
        self.s = int(s)
        self.left = find('outB')
        self.right = find('outC')
        self.g = find('outA')

    def _w(self, b, k, v):
        if not b:
            log.info('[SIM] %s=%s', k, v); return
        write(os.path.join(b, k), v)

    def drive(self, l, r):
        self._w(self.left, 'speed_sp', l); self._w(self.right, 'speed_sp', r)
        self._w(self.left, 'command', 'run-forever'); self._w(self.right, 'command', 'run-forever')

    def stop(self):
        self._w(self.left, 'command', 'stop'); self._w(self.right, 'command', 'stop')

    def grip(self, p):
        if not self.g: log.info('[SIM] grip %s', p); return
        self._w(self.g, 'speed_sp', '200'); self._w(self.g, 'position_sp', str(int(p))); self._w(self.g, 'command', 'run-to-rel-pos')

    def handle(self, c):
        c = c.strip().lower();
        if not c: return
        log.info('Cmd %s', c)
        if c == 'forward': self.drive(self.s, self.s)
        elif c == 'backward': self.drive(-self.s, -self.s)
        elif c == 'left': self.drive(-self.s, self.s)
        elif c == 'right': self.drive(self.s, -self.s)
        elif c == 'stop': self.stop()
        elif c == 'gripper_open': self.grip(90)
        elif c == 'gripper_close': self.grip(-90)


def ws_accept(k):
    return base64.b64encode(hashlib.sha1((k + WS_GUID).encode()).digest()).decode()


def recv_exact(s, n):
    d = b''
    while len(d) < n:
        chunk = s.recv(n - len(d))
        if not chunk: return None
        d += chunk
    return d


def read_text(s):
    h = recv_exact(s, 2)
    if not h: return None
    b1, b2 = struct.unpack('!BB', h)
    masked = b2 & 0x80
    ln = b2 & 0x7f
    if ln >= 126: return None
    m = recv_exact(s, 4) if masked else None
    p = recv_exact(s, ln) if ln else b''
    if p is None: return None
    if m:
        p = bytes(b ^ m[i % 4] for i, b in enumerate(p))
    return p.decode('utf-8', 'ignore')


def send_text(s, t):
    b = t.encode('utf-8'); l = len(b)
    s.sendall(bytes([0x81, l]) + b)


def serve(h, p, speed):
    r = R(speed); ls = socket.socket(); ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); ls.bind((h, p)); ls.listen(1)
    log.info('Listen ws://%s:%d', h, p)
    conn, a = ls.accept(); data = b''
    while b'\r\n\r\n' not in data:
        ch = conn.recv(1024);
        if not ch: return
        data += ch
    headers = data.decode('utf-8', 'ignore').split('\r\n')
    key = None
    for ln in headers:
        if ln.lower().startswith('sec-websocket-key:'): key = ln.split(':', 1)[1].strip(); break
    if not key: conn.close(); return
    conn.sendall(('HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: %s\r\n\r\n' % ws_accept(key)).encode())
    while True:
        msg = read_text(conn)
        if msg is None: break
        for ln in msg.splitlines():
            ln = ln.strip();
            if not ln: continue
            r.handle(ln)
            send_text(conn, 'ACK %s' % ln)
    try: conn.close()
    finally: ls.close()


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--host', default='0.0.0.0'); ap.add_argument('--port', type=int, default=8765); ap.add_argument('--speed', type=int, default=50)
    a = ap.parse_args(); serve(a.host, a.port, a.speed)
