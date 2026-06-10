from __future__ import annotations

import json
import math
import os
import platform
import random
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil

from PyQt6.QtCore import (
    QEasingCurve, QMimeData, QObject, QPointF, QRectF, QSize, Qt,
    QTimer, QUrl, pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush, QColor, QDragEnterEvent, QDropEvent, QFont, QFontDatabase,
    QKeySequence, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
    QRadialGradient, QShortcut, QConicalGradient, QPolygonF,
)
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QPushButton, QScrollArea, QSizePolicy, QTextEdit,
    QVBoxLayout, QWidget, QProgressBar, QGraphicsDropShadowEffect,
)


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR   = _base_dir()
CONFIG_DIR = BASE_DIR / "config"
API_FILE   = CONFIG_DIR / "api_keys.json"

_DEFAULT_W, _DEFAULT_H = 1200, 780
_MIN_W,     _MIN_H     = 960, 640
_LEFT_W  = 190
_RIGHT_W = 390

_OS = platform.system()


# ═══════════════════════════════════════════════════════════════════════════════
#  COLOUR PALETTE — Tony Stark holographic HUD
# ═══════════════════════════════════════════════════════════════════════════════
class C:
    BG         = "#00040a"       # near-black space
    PANEL      = "#000a12"
    PANEL2     = "#000c16"
    DARK       = "#00070e"
    BAR_BG     = "#010e1a"

    BORDER     = "#082030"
    BORDER_B   = "#0f4060"
    BORDER_A   = "#0a2c44"
    BORDER_HOT = "#1a6080"

    # Primary: arc-reactor electric cyan
    PRI        = "#00c8f0"
    PRI_DIM    = "#005870"
    PRI_GHO    = "#001220"
    PRI_BRIGHT = "#60e8ff"
    PRI_FLARE  = "#a0f4ff"

    # Orange / amber heat
    HOT        = "#ff7200"
    HOT_DIM    = "#7a3400"
    HOT_GLOW   = "#ff9940"

    # Gold data
    GOLD       = "#e8b400"
    GOLD_DIM   = "#6a5000"

    # Status
    GREEN      = "#00ff88"
    GREEN_D    = "#00994d"
    RED        = "#ff2244"
    MUTED_C    = "#ff2255"

    # Text hierarchy
    TEXT       = "#7ae8ff"
    TEXT_DIM   = "#1e5a70"
    TEXT_MED   = "#3a9ab8"
    TEXT_HOT   = "#ff9940"
    WHITE      = "#c8f4ff"

    # ACC2 kept for backward compat
    ACC2       = "#e8b400"
    ACC        = "#ff7200"


def qcol(h: str, a: int = 255) -> QColor:
    c = QColor(h); c.setAlpha(a); return c


# ═══════════════════════════════════════════════════════════════════════════════
#  SYSTEM METRICS (logic unchanged, same public API)
# ═══════════════════════════════════════════════════════════════════════════════
class _SysMetrics:
    def __init__(self):
        self.cpu = self.mem = self.net = 0.0
        self.gpu = self.tmp = -1.0
        self._lock        = threading.Lock()
        self._last_net    = psutil.net_io_counters()
        self._last_net_t  = time.time()
        self._running     = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while self._running:
            try: self._update()
            except Exception: pass
            time.sleep(1.5)

    def _update(self):
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent
        nc  = psutil.net_io_counters()
        now = time.time()
        dt  = now - self._last_net_t
        if dt > 0:
            net = ((nc.bytes_sent - self._last_net.bytes_sent) +
                   (nc.bytes_recv - self._last_net.bytes_recv)) / dt / (1024*1024)
        else:
            net = 0.0
        self._last_net = nc; self._last_net_t = now
        gpu = self._get_gpu(); tmp = self._get_temp()
        with self._lock:
            self.cpu=cpu; self.mem=mem; self.net=net; self.gpu=gpu; self.tmp=tmp

    def _get_gpu(self) -> float:
        try:
            r = subprocess.run(["nvidia-smi","--query-gpu=utilization.gpu",
                "--format=csv,noheader,nounits"], capture_output=True,text=True,timeout=2)
            if r.returncode == 0:
                v=[float(x.strip()) for x in r.stdout.strip().split("\n") if x.strip()]
                if v: return sum(v)/len(v)
        except Exception: pass
        if _OS == "Linux":
            try:
                r=subprocess.run(["rocm-smi","--showuse","--csv"],
                    capture_output=True,text=True,timeout=2)
                if r.returncode==0:
                    for ln in r.stdout.strip().split("\n"):
                        p=ln.split(",")
                        if len(p)>=2:
                            try: return float(p[1].strip().replace("%",""))
                            except ValueError: pass
            except Exception: pass
        if _OS == "Darwin":
            try:
                r=subprocess.run(["sudo","-n","powermetrics","-n","1","-i","500",
                    "--samplers","gpu_power"],capture_output=True,text=True,timeout=2)
                if r.returncode==0 and "GPU" in r.stdout:
                    import re; m=re.search(r'GPU\s+Active:\s+([\d.]+)%',r.stdout)
                    if m: return float(m.group(1))
            except Exception: pass
        return -1.0

    def _get_temp(self) -> float:
        try:
            temps=psutil.sensors_temperatures()
            for name in ["coretemp","k10temp","cpu_thermal","acpitz","cpu-thermal","zenpower","it8688"]:
                if name in temps and temps[name]: return temps[name][0].current
            for entries in temps.values():
                if entries: return entries[0].current
        except Exception: pass
        if _OS=="Darwin":
            try:
                r=subprocess.run(["osx-cpu-temp"],capture_output=True,text=True,timeout=2)
                if r.returncode==0:
                    import re; m=re.search(r"([\d.]+)",r.stdout)
                    if m: return float(m.group(1))
            except Exception: pass
        if _OS=="Windows":
            try:
                r=subprocess.run(["powershell","-Command",
                    "(Get-WmiObject MSAcpi_ThermalZoneTemperature -Namespace root/wmi).CurrentTemperature"],
                    capture_output=True,text=True,timeout=3)
                if r.returncode==0 and r.stdout.strip():
                    return float(r.stdout.strip().split("\n")[0])/10.0-273.15
            except Exception: pass
        return -1.0

    def snapshot(self) -> dict:
        with self._lock:
            return {"cpu":self.cpu,"mem":self.mem,"net":self.net,"gpu":self.gpu,"tmp":self.tmp}


_metrics = _SysMetrics()


# ═══════════════════════════════════════════════════════════════════════════════
#  DRAWING HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def _hex_pts(cx, cy, r, rot=0.0):
    return [QPointF(cx + r*math.cos(math.radians(60*i + rot)),
                    cy + r*math.sin(math.radians(60*i + rot))) for i in range(6)]

def _draw_hex(p: QPainter, cx, cy, r, rot=0.0):
    pts = _hex_pts(cx, cy, r, rot)
    path = QPainterPath(); path.moveTo(pts[0])
    for pt in pts[1:]: path.lineTo(pt)
    path.closeSubpath(); p.drawPath(path)

def _draw_ngon(p: QPainter, cx, cy, r, n, rot=0.0):
    pts = [QPointF(cx+r*math.cos(math.radians(360/n*i+rot)),
                   cy+r*math.sin(math.radians(360/n*i+rot))) for i in range(n)]
    path = QPainterPath(); path.moveTo(pts[0])
    for pt in pts[1:]: path.lineTo(pt)
    path.closeSubpath(); p.drawPath(path)


# ═══════════════════════════════════════════════════════════════════════════════
#  HUD CANVAS — full Stark-tech holographic display
# ═══════════════════════════════════════════════════════════════════════════════
class HudCanvas(QWidget):
    def __init__(self, face_path: str, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMinimumSize(340, 340)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.muted    = False
        self.speaking = False
        self.state    = "INITIALISING"

        self._tick      = 0
        self._scale     = 1.0; self._tgt_scale = 1.0
        self._halo      = 55.0; self._tgt_halo = 55.0
        self._last_t    = time.time()

        # ring rotations — 8 rings
        self._rings     = [i * 45.0 for i in range(8)]
        self._scan      = [0.0, 180.0, 90.0, 270.0]   # 4 scanners
        self._pulses:  list[float] = [0.0, 60.0, 120.0]
        self._hexring:  list[float] = []

        # floating data panels
        self._data_nodes: list[dict] = []
        self._init_data_nodes()

        # particles & streams
        self._particles: list[list] = []
        self._bits:      list[list] = []   # floating binary bits

        # waveform history
        self._wave = [0.0] * 48

        self._blink = True; self._blink_tick = 0

        self._face_px: QPixmap | None = None
        self._load_face(face_path)

        # background hex grid
        self._bg_hexes: list[tuple] = []
        self._gen_bg_hexes()

        self._tmr = QTimer(self); self._tmr.timeout.connect(self._step); self._tmr.start(16)

    # ── init helpers ──────────────────────────────────────────────────────────
    def _gen_bg_hexes(self):
        pts = []
        sz = 38
        for col in range(-1, 32):
            for row in range(-1, 22):
                x = col * sz * 1.732 + (row % 2) * sz * 0.866
                y = row * sz * 1.5
                pts.append((x, y, sz * 0.9))
        self._bg_hexes = pts

    def _init_data_nodes(self):
        """Floating data readout labels scattered around the HUD."""
        self._data_nodes = [
            {"key": "SYS.CORE",   "val": "ONLINE",    "angle": 42,  "dist": 0.70, "col": C.PRI},
            {"key": "NEURAL.NET", "val": "ACTIVE",    "angle": 138, "dist": 0.68, "col": C.GREEN},
            {"key": "THREAT.LVL", "val": "MINIMAL",   "angle": 218, "dist": 0.72, "col": C.GOLD},
            {"key": "PWR.CORE",   "val": "98.7%",     "angle": 318, "dist": 0.69, "col": C.HOT},
            {"key": "UPLINK",     "val": "SECURE",    "angle": 82,  "dist": 0.78, "col": C.PRI_BRIGHT},
            {"key": "FIREWALL",   "val": "ENGAGED",   "angle": 262, "dist": 0.76, "col": C.GREEN},
        ]

    def _load_face(self, path: str):
        try:
            from PIL import Image, ImageDraw
            import io
            img = Image.open(path).convert("RGBA")
            sz = min(img.size); img = img.resize((sz,sz),Image.LANCZOS)
            mk = Image.new("L",(sz,sz),0)
            ImageDraw.Draw(mk).ellipse((2,2,sz-2,sz-2),fill=255)
            img.putalpha(mk)
            buf = io.BytesIO(); img.save(buf,format="PNG")
            px = QPixmap(); px.loadFromData(buf.getvalue()); self._face_px = px
        except Exception:
            self._face_px = None

    # ── animation step ────────────────────────────────────────────────────────
    def _step(self):
        self._tick += 1
        now = time.time()

        # halo pulsing
        if now - self._last_t > (0.09 if self.speaking else 0.42):
            if self.speaking:
                self._tgt_scale = random.uniform(1.07, 1.18)
                self._tgt_halo  = random.uniform(170, 210)
            elif self.muted:
                self._tgt_scale = random.uniform(0.996, 1.002)
                self._tgt_halo  = random.uniform(10, 22)
            else:
                self._tgt_scale = random.uniform(1.001, 1.010)
                self._tgt_halo  = random.uniform(52, 78)
            self._last_t = now

        sp = 0.42 if self.speaking else 0.14
        self._scale += (self._tgt_scale - self._scale) * sp
        self._halo  += (self._tgt_halo  - self._halo)  * sp

        # ring rotation speeds (alternating CW/CCW)
        spds = ([1.6,-1.1,2.4,-0.7,1.9,-1.3,2.8,-0.5] if self.speaking
                else [0.55,-0.38,0.92,-0.28,0.70,-0.45,1.10,-0.20])
        for i,s in enumerate(spds):
            self._rings[i] = (self._rings[i] + s) % 360

        # scanner rotation
        ss = ([3.5,-2.2,1.8,-2.8] if self.speaking else [1.4,-0.9,0.7,-1.1])
        for i,s in enumerate(ss):
            self._scan[i] = (self._scan[i] + s) % 360

        # radial pulses
        fw = min(self.width(), self.height())
        lim = fw * 0.78
        spd = 5.0 if self.speaking else 2.2
        self._pulses = [r+spd for r in self._pulses if r+spd < lim]
        if len(self._pulses) < 4 and random.random() < (0.10 if self.speaking else 0.030):
            self._pulses.append(0.0)

        # hex ring pulses
        self._hexring = [r+1.6 for r in self._hexring if r+1.6 < fw*0.65]
        if len(self._hexring) < 3 and random.random() < 0.018:
            self._hexring.append(0.0)

        # particles (speaking mode)
        if self.speaking and random.random() < 0.35:
            cx,cy = self.width()/2, self.height()/2
            ang = random.uniform(0, 2*math.pi)
            rs  = fw * 0.29
            self._particles.append([
                cx+math.cos(ang)*rs, cy+math.sin(ang)*rs,
                math.cos(ang)*random.uniform(1.2,3.0),
                math.sin(ang)*random.uniform(1.2,3.0)-0.5, 1.0,
                random.choice([C.PRI,C.HOT,C.GOLD,C.GREEN])
            ])
        self._particles = [[p[0]+p[2],p[1]+p[3],p[2]*0.95,p[3]*0.95,p[4]-0.024,p[5]]
                           for p in self._particles if p[4]>0]

        # floating binary bits
        if self._tick % 3 == 0 and random.random() < 0.40:
            cx = self.width()/2
            x  = cx + random.uniform(-fw*0.55, fw*0.55)
            col = random.choice([C.PRI_DIM, C.BORDER_HOT, C.GOLD_DIM])
            self._bits.append([x, random.uniform(0,self.height()*0.2),
                                random.uniform(0.8,2.2), 1.0, col])
        self._bits = [[b[0],b[1]+b[2],b[2],b[3]-0.016,b[4]]
                      for b in self._bits if b[3]>0 and b[1]<self.height()]

        # waveform update
        if self.speaking:
            self._wave.append(random.uniform(4, 28))
        else:
            self._wave.append(3 + 2.2*math.sin(self._tick*0.07 + len(self._wave)*0.4))
        if len(self._wave) > 48: self._wave.pop(0)

        # update data node values occasionally
        if self._tick % 90 == 0:
            snap = _metrics.snapshot()
            self._data_nodes[3]["val"] = f"{snap['cpu']:.0f}%"

        self._blink_tick += 1
        if self._blink_tick >= 32:
            self._blink = not self._blink; self._blink_tick = 0
        self.update()

    # ── PAINT ─────────────────────────────────────────────────────────────────
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), qcol(C.BG))

        W, H = self.width(), self.height()
        cx, cy = W/2, H/2
        fw = min(W, H)

        self._paint_bg(p, W, H, cx, cy, fw)
        self._paint_outer_rings(p, cx, cy, fw)
        self._paint_scanners(p, cx, cy, fw)
        self._paint_tick_ring(p, cx, cy, fw)
        self._paint_crosshair(p, cx, cy, fw)
        self._paint_brackets(p, cx, cy, fw)
        self._paint_hex_rings(p, cx, cy, fw)
        self._paint_pulses(p, cx, cy, fw)
        self._paint_bits(p)
        self._paint_face(p, cx, cy, fw)
        self._paint_particles(p)
        self._paint_data_nodes(p, cx, cy, fw)
        self._paint_status(p, cx, cy, W, H, fw)
        self._paint_waveform(p, cx, cy, W, H, fw)

    def _paint_bg(self, p, W, H, cx, cy, fw):
        # hexagonal dot grid
        for (hx, hy, hr) in self._bg_hexes:
            dist = math.hypot(hx - cx, hy - cy)
            alpha = max(0, int(28 - dist / fw * 20))
            if alpha <= 0: continue
            p.setPen(QPen(qcol(C.BORDER, alpha), 0.6))
            p.setBrush(Qt.BrushStyle.NoBrush)
            _draw_hex(p, hx, hy, hr * 0.28, 30)

        # deep radial glow from centre
        rg = QRadialGradient(cx, cy, fw * 0.72)
        rg.setColorAt(0.0, QColor(0, 30, 50, 40))
        rg.setColorAt(0.45, QColor(0, 15, 28, 20))
        rg.setColorAt(1.0,  QColor(0, 4, 10, 180))
        p.fillRect(self.rect(), QBrush(rg))

        # moving scan line sweep
        sl_y = int((self._tick * 2.1) % H)
        for dy in range(4):
            a = [18, 10, 5, 2][dy]
            p.setPen(QPen(qcol(C.PRI, a), 1))
            p.drawLine(0, sl_y + dy, W, sl_y + dy)

        # horizontal grid lines (faint)
        for y in range(0, H, 32):
            a = 8 + int(5 * math.sin(y * 0.04 + self._tick * 0.02))
            p.setPen(QPen(qcol(C.BORDER, a), 0.5))
            p.drawLine(0, y, W, y)

    def _paint_outer_rings(self, p, cx, cy, fw):
        ring_specs = [
            # (radius_frac, width, arc_len, gap, color_key, alt_color)
            (0.499, 2.8, 88,  55, C.PRI,    None),
            (0.462, 1.8, 62,  42, C.BORDER_HOT, C.HOT),
            (0.420, 2.2, 50,  35, C.PRI_DIM, C.PRI),
            (0.378, 1.4, 38,  28, C.GOLD_DIM, C.GOLD),
            (0.336, 1.8, 72,  48, C.PRI,    None),
            (0.292, 1.2, 30,  22, C.BORDER_HOT, C.HOT),
            (0.248, 1.0, 24,  18, C.PRI_DIM, None),
            (0.204, 0.8, 18,  14, C.GOLD_DIM, None),
        ]
        for idx, (rfrac, rw, arc_l, gap, base_c, alt_c) in enumerate(ring_specs):
            rr   = fw * rfrac
            base = self._rings[idx]
            frac = 1.0 - idx * 0.10
            av   = max(0, min(255, int(self._halo * frac)))
            # primary colour arcs
            p.setPen(QPen(qcol(base_c, av), rw))
            p.setBrush(Qt.BrushStyle.NoBrush)
            rect = QRectF(cx-rr, cy-rr, rr*2, rr*2)
            a = base
            while a < base + 360:
                p.drawArc(rect, int(a*16), int(arc_l*16))
                a += arc_l + gap
            # accent colour arcs (offset)
            if alt_c:
                p.setPen(QPen(qcol(alt_c, av // 2), rw * 0.6))
                a2 = base + arc_l + gap/2
                while a2 < base + 360:
                    p.drawArc(rect, int(a2*16), int((arc_l//3)*16))
                    a2 += arc_l + gap

    def _paint_scanners(self, p, cx, cy, fw):
        sr = fw * 0.514
        sa = min(255, int(self._halo * 1.7))
        srect = QRectF(cx-sr, cy-sr, sr*2, sr*2)
        # scanner 0 — wide cyan
        p.setPen(QPen(qcol(C.PRI, sa), 3.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        ex0 = 92 if self.speaking else 55
        p.drawArc(srect, int(self._scan[0]*16), int(ex0*16))
        # scanner sweep fill (gradient-like layering)
        for i in range(1, 5):
            a_lay = max(0, sa - i*40)
            p.setPen(QPen(qcol(C.PRI, a_lay), 2.0 - i*0.3))
            p.drawArc(srect, int((self._scan[0]-i*4)*16), int((ex0+i*3)*16))
        # scanner 1 — hot orange
        p.setPen(QPen(qcol(C.HOT, sa//2), 2.0))
        p.drawArc(srect, int(self._scan[1]*16), int(38*16))
        # scanner 2 — gold (inner)
        sr2 = fw * 0.455
        sr2rect = QRectF(cx-sr2, cy-sr2, sr2*2, sr2*2)
        p.setPen(QPen(qcol(C.GOLD, sa//3), 1.6))
        p.drawArc(sr2rect, int(self._scan[2]*16), int(28*16))
        # scanner 3 — dim cyan counter-rotate
        p.setPen(QPen(qcol(C.PRI_DIM, sa//4), 1.2))
        p.drawArc(sr2rect, int(self._scan[3]*16), int(18*16))

    def _paint_tick_ring(self, p, cx, cy, fw):
        t_out = fw * 0.499
        for deg in range(0, 360, 3):
            rad = math.radians(deg)
            if deg % 30 == 0:
                t_in, pw, al = t_out - 16, 2.2, 220
            elif deg % 10 == 0:
                t_in, pw, al = t_out - 9,  1.6, 160
            elif deg % 5 == 0:
                t_in, pw, al = t_out - 5,  1.0, 100
            else:
                t_in, pw, al = t_out - 3,  0.6, 55
            p.setPen(QPen(qcol(C.PRI, al), pw))
            p.drawLine(
                QPointF(cx + t_out*math.cos(rad), cy - t_out*math.sin(rad)),
                QPointF(cx + t_in *math.cos(rad), cy - t_in *math.sin(rad)),
            )
        # degree numerals at major ticks
        p.setFont(QFont("Courier New", 5))
        for deg in range(0, 360, 30):
            rad = math.radians(deg)
            tx = cx + (t_out - 22)*math.cos(rad) - 8
            ty = cy - (t_out - 22)*math.sin(rad) - 5
            p.setPen(QPen(qcol(C.TEXT_DIM, 120), 1))
            p.drawText(QRectF(tx, ty, 16, 10), Qt.AlignmentFlag.AlignCenter, str(deg))

    def _paint_crosshair(self, p, cx, cy, fw):
        ch_r, gap = fw * 0.526, fw * 0.178
        al = int(self._halo * 0.60)
        # main cross arms
        p.setPen(QPen(qcol(C.PRI, al), 1.4))
        p.drawLine(QPointF(cx-ch_r,cy), QPointF(cx-gap,cy))
        p.drawLine(QPointF(cx+gap, cy), QPointF(cx+ch_r,cy))
        p.drawLine(QPointF(cx,cy-ch_r), QPointF(cx,cy-gap))
        p.drawLine(QPointF(cx,cy+gap),  QPointF(cx,cy+ch_r))
        # diagonal sub-arms
        d = gap * 0.72
        p.setPen(QPen(qcol(C.PRI, al//2), 0.9))
        for ang in [45, 135, 225, 315]:
            rd = math.radians(ang)
            p.drawLine(QPointF(cx+d*math.cos(rd), cy-d*math.sin(rd)),
                       QPointF(cx+ch_r*0.74*math.cos(rd), cy-ch_r*0.74*math.sin(rd)))
        # tiny centre diamond
        ds = fw * 0.012
        p.setPen(QPen(qcol(C.PRI_BRIGHT, min(255,int(self._halo*1.8))), 1.2))
        p.setBrush(QBrush(qcol(C.PRI, min(255, int(self._halo*0.4)))))
        diam = QPolygonF([QPointF(cx,cy-ds), QPointF(cx+ds,cy),
                          QPointF(cx,cy+ds), QPointF(cx-ds,cy)])
        p.drawPolygon(diam)

    def _paint_brackets(self, p, cx, cy, fw):
        # outer hex frame
        p.setPen(QPen(qcol(C.BORDER_HOT, 70), 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        _draw_hex(p, cx, cy, fw*0.538, 0)

        # corner L-brackets
        bl  = 36; bl2 = 14
        hl  = cx - fw*0.538*math.cos(math.radians(30))
        hr  = cx + fw*0.538*math.cos(math.radians(30))
        ht  = cy - fw*0.538; hb = cy + fw*0.538

        p.setPen(QPen(qcol(C.PRI, 230), 2.4))
        for bx, by, dx, dy in [(hl,ht,1,1),(hr,ht,-1,1),(hl,hb,1,-1),(hr,hb,-1,-1)]:
            p.drawLine(QPointF(bx,by), QPointF(bx+dx*bl,by))
            p.drawLine(QPointF(bx,by), QPointF(bx,by+dy*bl))
        # secondary tick-out lines
        p.setPen(QPen(qcol(C.GOLD, 140), 1.2))
        for bx, by, dx, dy in [(hl,ht,1,1),(hr,ht,-1,1),(hl,hb,1,-1),(hr,hb,-1,-1)]:
            p.drawLine(QPointF(bx+dx*(bl+4),by), QPointF(bx+dx*(bl+bl2),by))
            p.drawLine(QPointF(bx,by+dy*(bl+4)), QPointF(bx,by+dy*(bl+bl2)))

        # mid-edge small markers
        for ang in [0, 60, 120, 180, 240, 300]:
            rd = math.radians(ang)
            mx = cx + fw*0.538*math.cos(rd); my = cy + fw*0.538*math.sin(rd)
            p.setPen(QPen(qcol(C.HOT, 140), 1.6))
            ml = 10
            p.drawLine(QPointF(mx - math.sin(rd)*ml, my + math.cos(rd)*ml),
                       QPointF(mx + math.sin(rd)*ml, my - math.cos(rd)*ml))

    def _paint_hex_rings(self, p, cx, cy, fw):
        for hr in self._hexring:
            a = max(0, int(160*(1.0 - hr/(fw*0.65))))
            col = qcol(C.HOT if self.speaking else C.PRI, a)
            p.setPen(QPen(col, 1.4)); p.setBrush(Qt.BrushStyle.NoBrush)
            _draw_hex(p, cx, cy, hr, self._tick * 0.5)

    def _paint_pulses(self, p, cx, cy, fw):
        for pr in self._pulses:
            a = max(0, int(255*(1.0 - pr/(fw*0.78))))
            col = qcol(C.MUTED_C if self.muted else (C.HOT if self.speaking else C.PRI), a)
            p.setPen(QPen(col, 1.6)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx-pr, cy-pr, pr*2, pr*2))

    def _paint_bits(self, p):
        p.setFont(QFont("Courier New", 6))
        for b in self._bits:
            a = max(0, int(b[3]*180))
            p.setPen(QPen(qcol(b[4], a), 1))
            p.drawText(QPointF(b[0],b[1]), random.choice("01"))

    def _paint_face(self, p, cx, cy, fw):
        if self._face_px:
            fsz = int(fw * 0.60 * self._scale)
            # face glow aura
            for i in range(8, 0, -1):
                ar = fsz * 0.56 * (1 + i*0.04)
                aa = max(0, int(self._halo * 0.06 * (1 - i/8)))
                gc = qcol(C.HOT if self.muted else C.PRI, aa)
                p.setPen(QPen(gc, 1)); p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QRectF(cx-ar, cy-ar, ar*2, ar*2))
            scaled = self._face_px.scaled(fsz,fsz,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap(int(cx-fsz/2), int(cy-fsz/2), scaled)
        else:
            # arc-reactor orb
            orb_r = int(fw * 0.27 * self._scale)
            for i in range(12, 0, -1):
                r2  = int(orb_r * i/12)
                frc = i/12
                if self.muted:   oc=(160,0,30)
                elif self.speaking: oc=(0,70,130)
                else:            oc=(0,52,90)
                aa = max(0,min(255,int(self._halo*1.2*frc)))
                p.setBrush(QBrush(QColor(int(oc[0]*frc),int(oc[1]*frc),int(oc[2]*frc),aa)))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QRectF(cx-r2,cy-r2,r2*2,r2*2))
            # arc reactor inner geometry: overlapping triangles + hexagon
            react_r = orb_r * 0.55
            p.setPen(QPen(qcol(C.PRI, min(255,int(self._halo*1.6))), 1.4))
            p.setBrush(Qt.BrushStyle.NoBrush)
            _draw_hex(p, cx, cy, react_r * 0.62, self._tick * 0.4)
            _draw_ngon(p, cx, cy, react_r, 3, self._tick * 0.8)
            _draw_ngon(p, cx, cy, react_r, 3, self._tick * 0.8 + 60)
            # core glow dot
            cr = orb_r * 0.18
            cg = QRadialGradient(cx, cy, cr)
            c1 = QColor(C.PRI_BRIGHT); c1.setAlpha(min(255,int(self._halo*2)))
            c2 = QColor(C.PRI); c2.setAlpha(0)
            cg.setColorAt(0.0,c1); cg.setColorAt(1.0,c2)
            p.setBrush(QBrush(cg)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(cx-cr,cy-cr,cr*2,cr*2))
            # label
            p.setPen(QPen(qcol(C.PRI,min(255,int(self._halo*2.2))),1.2))
            p.setFont(QFont("Courier New",15,QFont.Weight.Bold))
            p.drawText(QRectF(cx-100,cy-18,200,36),Qt.AlignmentFlag.AlignCenter,"J.A.R.V.I.S")

    def _paint_particles(self, p):
        for pt in self._particles:
            a = max(0, min(255, int(pt[4]*255)))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(qcol(pt[5], a)))
            p.drawEllipse(QPointF(pt[0],pt[1]), 3.0, 3.0)

    def _paint_data_nodes(self, p, cx, cy, fw):
        """Floating telemetry labels with connector lines."""
        for node in self._data_nodes:
            ang = math.radians(node["angle"] + self._tick * 0.04)
            d   = fw * node["dist"]
            nx  = cx + math.cos(ang)*d
            ny  = cy + math.sin(ang)*d
            # connector line to edge of face
            face_r = fw * 0.31
            fx = cx + math.cos(ang)*face_r
            fy = cy + math.sin(ang)*face_r
            p.setPen(QPen(qcol(node["col"], 60), 0.8))
            p.drawLine(QPointF(fx,fy), QPointF(nx,ny))
            # node box
            tw, th = 82, 26
            bx, by = nx - tw/2, ny - th/2
            bg = QLinearGradient(bx,by,bx+tw,by+th)
            bc = QColor(node["col"]); bc.setAlpha(18)
            bg.setColorAt(0.0,bc); bg.setColorAt(1.0,QColor(0,0,0,0))
            p.fillRect(QRectF(bx,by,tw,th), QBrush(bg))
            p.setPen(QPen(qcol(node["col"], 100), 0.8))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(QRectF(bx,by,tw,th))
            # text
            p.setFont(QFont("Courier New",5,QFont.Weight.Bold))
            p.setPen(QPen(qcol(node["col"],140),1))
            p.drawText(QRectF(bx+2,by+1,tw-4,10), Qt.AlignmentFlag.AlignCenter, node["key"])
            p.setFont(QFont("Courier New",7,QFont.Weight.Bold))
            p.setPen(QPen(qcol(node["col"],220),1))
            p.drawText(QRectF(bx+2,by+12,tw-4,12), Qt.AlignmentFlag.AlignCenter, node["val"])
            # corner accents on box
            p.setPen(QPen(qcol(node["col"],180),1.2))
            cl = 5
            for (x0,y0,dx,dy) in [(bx,by,1,1),(bx+tw,by,-1,1),(bx,by+th,1,-1),(bx+tw,by+th,-1,-1)]:
                p.drawLine(QPointF(x0,y0),QPointF(x0+dx*cl,y0))
                p.drawLine(QPointF(x0,y0),QPointF(x0,y0+dy*cl))

    def _paint_status(self, p, cx, cy, W, H, fw):
        sy = cy + fw * 0.425
        if self.muted:
            txt, col = "⊘  MUTED",      qcol(C.MUTED_C)
        elif self.speaking:
            txt, col = "●  SPEAKING",   qcol(C.HOT_GLOW)
        elif self.state == "THINKING":
            sym = "◈" if self._blink else "◇"
            txt, col = f"{sym}  THINKING",   qcol(C.GOLD)
        elif self.state == "PROCESSING":
            sym = "▷" if self._blink else "▶"
            txt, col = f"{sym}  PROCESSING", qcol(C.GOLD)
        elif self.state == "LISTENING":
            sym = "●" if self._blink else "○"
            txt, col = f"{sym}  LISTENING",  qcol(C.GREEN)
        else:
            sym = "●" if self._blink else "○"
            txt, col = f"{sym}  {self.state}", qcol(C.PRI)

        # glow pill underlay
        pill_w, pill_h = 220, 30
        pill = QRectF(cx-pill_w/2, sy-2, pill_w, pill_h)
        pg = QLinearGradient(cx-pill_w/2, sy, cx+pill_w/2, sy)
        fc = QColor(col); fc.setAlpha(0)
        mc = QColor(col); mc.setAlpha(30)
        pg.setColorAt(0,fc); pg.setColorAt(0.5,mc); pg.setColorAt(1,fc)
        p.fillRect(pill, QBrush(pg))
        # top/bottom lines
        p.setPen(QPen(col, 0.8)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(cx-pill_w/2+10,sy-1),QPointF(cx+pill_w/2-10,sy-1))
        p.drawLine(QPointF(cx-pill_w/2+10,sy+pill_h-1),QPointF(cx+pill_w/2-10,sy+pill_h-1))

        p.setPen(QPen(col, 1.2))
        p.setFont(QFont("Courier New",12,QFont.Weight.Bold))
        p.drawText(pill, Qt.AlignmentFlag.AlignCenter, txt)

    def _paint_waveform(self, p, cx, cy, W, H, fw):
        wy = cy + fw * 0.462
        N  = len(self._wave)
        bw = 7
        wx0 = cx - N*bw/2
        max_h = 30
        for i, hgt_f in enumerate(self._wave):
            hgt = min(max_h, hgt_f)
            if self.muted:
                cl = qcol(C.MUTED_C, 100)
            elif self.speaking:
                cl = qcol(C.HOT_GLOW if hgt > 16 else C.PRI, 210)
            else:
                cl = qcol(C.PRI_DIM, 160)
            rect = QRectF(wx0+i*bw, wy+max_h-hgt, bw-1, hgt)
            wg = QLinearGradient(0, wy+max_h-hgt, 0, wy+max_h)
            wg.setColorAt(0.0, cl); wg.setColorAt(1.0, QColor(cl.red(),cl.green(),cl.blue(),30))
            p.fillRect(rect, QBrush(wg))


# ═══════════════════════════════════════════════════════════════════════════════
#  METRIC BAR — holographic data bar with animated fill
# ═══════════════════════════════════════════════════════════════════════════════
class MetricBar(QWidget):
    def __init__(self, label: str, color: str = C.PRI, parent=None):
        super().__init__(parent)
        self._label = label; self._color = color
        self._value = 0.0; self._anim = 0.0; self._text = "--"
        self.setFixedHeight(44); self.setMinimumWidth(80)
        t = QTimer(self); t.timeout.connect(self._tick); t.start(28)

    def _tick(self):
        if abs(self._anim - self._value) > 0.2:
            self._anim += (self._value - self._anim) * 0.13
            self.update()

    def set_value(self, pct: float, text: str):
        self._value = max(0.0, min(100.0, pct)); self._text = text; self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # panel bg
        bg = QLinearGradient(0,0,W,H)
        bg.setColorAt(0.0, qcol(C.PANEL2)); bg.setColorAt(1.0, qcol(C.DARK))
        p.setBrush(QBrush(bg))
        p.setPen(QPen(qcol(C.BORDER_A), 0.8))
        p.drawRoundedRect(QRectF(1,1,W-2,H-2), 3,3)

        # left accent line
        if self._anim > 85: ac = C.RED
        elif self._anim > 65: ac = C.HOT
        else: ac = self._color
        p.setPen(QPen(qcol(ac,200), 2.5))
        p.drawLine(QPointF(1,4), QPointF(1,H-4))

        bh=5; by=H-bh-7; bw=W-16; bx=8; fw=int(bw*self._anim/100)
        # trough
        p.setBrush(QBrush(qcol(C.BAR_BG))); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(bx,by,bw,bh),2.5,2.5)
        # fill
        if fw > 0:
            fg = QLinearGradient(bx,0,bx+fw,0)
            dim = QColor(ac); dim.setAlpha(80); bright=QColor(ac); bright.setAlpha(255)
            fg.setColorAt(0,dim); fg.setColorAt(1,bright)
            p.setBrush(QBrush(fg)); p.drawRoundedRect(QRectF(bx,by,fw,bh),2.5,2.5)
            # glow pip
            p.setBrush(QBrush(qcol(C.WHITE,200))); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(bx+fw-2.5, by-1, 5, bh+2))

        p.setFont(QFont("Courier New",7,QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.TEXT_DIM),1))
        p.drawText(QRectF(10,4,55,14),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,self._label)

        p.setFont(QFont("Courier New",9,QFont.Weight.Bold))
        p.setPen(QPen(qcol(ac) if self._text!="--" else qcol(C.TEXT_DIM),1))
        p.drawText(QRectF(0,3,W-8,16),Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter,self._text)


# ═══════════════════════════════════════════════════════════════════════════════
#  LOG WIDGET — typewriter with coloured tags
# ═══════════════════════════════════════════════════════════════════════════════
class LogWidget(QTextEdit):
    _sig = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Courier New", 9))
        self.setStyleSheet(f"""
            QTextEdit {{
                background: {C.PANEL};
                color: {C.TEXT};
                border: 1px solid {C.BORDER_A};
                border-radius: 4px;
                padding: 8px;
                selection-background-color: {C.PRI_GHO};
            }}
            QScrollBar:vertical {{
                background: {C.BG}; width: 6px; border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {C.BORDER_HOT}; border-radius: 3px; min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        """)
        self._queue: list[str] = []
        self._typing = False; self._text = ""; self._pos = 0; self._tag = "sys"
        self._tmr = QTimer(self); self._tmr.timeout.connect(self._step)
        self._sig.connect(self._enqueue)

    def append_log(self, text: str):
        self._sig.emit(text)

    def _enqueue(self, text: str):
        self._queue.append(text)
        if not self._typing: self._next()

    def _next(self):
        if not self._queue:
            self._typing = False; return
        self._typing = True; self._text = self._queue.pop(0); self._pos = 0
        tl = self._text.lower()
        if   tl.startswith("you:"):    self._tag = "you"
        elif tl.startswith("jarvis:"): self._tag = "ai"
        elif tl.startswith("file:"):   self._tag = "file"
        elif "err" in tl:              self._tag = "err"
        else:                          self._tag = "sys"
        self._tmr.start(5)

    def _step(self):
        if self._pos < len(self._text):
            ch  = self._text[self._pos]
            cur = self.textCursor(); fmt = cur.charFormat()
            col = {"you":qcol(C.WHITE),"ai":qcol(C.PRI_BRIGHT),"err":qcol(C.RED),
                   "file":qcol(C.GREEN),"sys":qcol(C.GOLD)}.get(self._tag, qcol(C.TEXT))
            fmt.setForeground(QBrush(col))
            cur.movePosition(cur.MoveOperation.End); cur.insertText(ch, fmt)
            self.setTextCursor(cur); self.ensureCursorVisible(); self._pos += 1
        else:
            self._tmr.stop(); cur = self.textCursor()
            cur.movePosition(cur.MoveOperation.End); cur.insertText("\n")
            self.setTextCursor(cur); self.ensureCursorVisible()
            QTimer.singleShot(20, self._next)


# ═══════════════════════════════════════════════════════════════════════════════
#  FILE UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════
_FILE_ICONS = {
    "image":("🖼","#00d4ff"),"video":("🎬","#ff6b00"),"audio":("🎵","#cc44ff"),
    "pdf":("📄","#ff4444"),"word":("📝","#4488ff"),"excel":("📊","#44bb44"),
    "code":("💻","#ffcc00"),"archive":("📦","#ff8844"),"pptx":("📊","#ff6622"),
    "text":("📃","#aaaaaa"),"data":("🔧","#88ddff"),"unknown":("📎","#888888"),
}
_EXT_TO_CAT = {
    **dict.fromkeys(["jpg","jpeg","png","gif","webp","bmp","tiff","svg","ico"],"image"),
    **dict.fromkeys(["mp4","avi","mov","mkv","wmv","flv","webm","m4v"],"video"),
    **dict.fromkeys(["mp3","wav","ogg","m4a","aac","flac","wma","opus"],"audio"),
    **dict.fromkeys(["pdf"],"pdf"),**dict.fromkeys(["doc","docx"],"word"),
    **dict.fromkeys(["xls","xlsx","ods"],"excel"),**dict.fromkeys(["ppt","pptx"],"pptx"),
    **dict.fromkeys(["py","js","ts","jsx","tsx","html","css","java","c","cpp","cs","go","rs","rb","php","swift","kt","sh","sql","lua"],"code"),
    **dict.fromkeys(["zip","rar","tar","gz","7z","bz2","xz"],"archive"),
    **dict.fromkeys(["txt","md","rst","log"],"text"),
    **dict.fromkeys(["csv","tsv","json","xml"],"data"),
}

def _file_category(path: Path) -> str:
    return _EXT_TO_CAT.get(path.suffix.lower().lstrip("."), "unknown")

def _fmt_size(size: int) -> str:
    if size<1024: return f"{size} B"
    elif size<1024**2: return f"{size/1024:.1f} KB"
    elif size<1024**3: return f"{size/1024**2:.1f} MB"
    else: return f"{size/1024**3:.1f} GB"


# ═══════════════════════════════════════════════════════════════════════════════
#  FILE DROP ZONE — holographic target
# ═══════════════════════════════════════════════════════════════════════════════
class FileDropZone(QWidget):
    file_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(115)
        self._current_file: str | None = None
        self._hovering = self._drag_over = False
        self._dash_offset = 0.0; self._ring_r = 0.0
        self._anim_tmr = QTimer(self); self._anim_tmr.timeout.connect(self._animate)
        self._anim_tmr.start(33)
        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)
        self._canvas = _DropCanvas(self); lay.addWidget(self._canvas)

    def _animate(self):
        self._dash_offset = (self._dash_offset + 1.1) % 26
        self._ring_r = (self._ring_r + 1.5) % max(1, self.height())
        self._canvas.update()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction(); self._drag_over = True; self._canvas.update()
    def dragLeaveEvent(self, e):
        self._drag_over = False; self._canvas.update()
    def dropEvent(self, e):
        self._drag_over = False
        if e.mimeData().hasUrls():
            path = e.mimeData().urls()[0].toLocalFile()
            if Path(path).is_file(): self._set_file(path)
        self._canvas.update()
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self._browse()
    def enterEvent(self, e): self._hovering = True; self._canvas.update()
    def leaveEvent(self, e): self._hovering = False; self._canvas.update()
    def current_file(self): return self._current_file
    def clear_file(self): self._current_file = None; self._canvas.update()

    def _browse(self):
        path,_ = QFileDialog.getOpenFileName(
            self, "Select a file for JARVIS", str(Path.home()),
            "All Files (*.*);;"
            "Images (*.jpg *.jpeg *.png *.gif *.webp *.bmp *.svg);;"
            "Documents (*.pdf *.docx *.txt *.md *.pptx);;"
            "Data (*.csv *.xlsx *.json *.xml);;"
            "Code (*.py *.js *.ts *.html *.css *.java *.cpp *.go);;"
            "Audio (*.mp3 *.wav *.ogg *.m4a *.aac *.flac);;"
            "Video (*.mp4 *.avi *.mov *.mkv *.wmv *.webm);;"
            "Archives (*.zip *.rar *.tar *.gz *.7z)")
        if path: self._set_file(path)

    def _set_file(self, path):
        self._current_file = path; self._canvas.update(); self.file_selected.emit(path)


class _DropCanvas(QWidget):
    def __init__(self, zone):
        super().__init__(zone); self._z = zone

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        z = self._z; W,H = self.width(),self.height(); pad=8
        rect = QRectF(pad,pad,W-pad*2,H-pad*2)

        # bg gradient
        if z._drag_over: bc="#002030"
        elif z._hovering: bc="#001525"
        else: bc=C.PANEL
        bg=QLinearGradient(0,0,W,H); c1=QColor(bc); c2=QColor(C.DARK)
        bg.setColorAt(0,c1); bg.setColorAt(1,c2)
        p.setBrush(QBrush(bg)); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect,6,6)

        # animated pulse ring inside zone
        if not z._current_file:
            pr = z._ring_r % (H * 0.5)
            pa = max(0, int(60*(1.0 - pr/(H*0.5))))
            pc = C.PRI if not z._drag_over else C.HOT_GLOW
            p.setPen(QPen(qcol(pc, pa), 1)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(W/2-pr,H/2-pr,pr*2,pr*2))

        # border
        if z._current_file: bc2=qcol(C.GREEN,220)
        elif z._drag_over:  bc2=qcol(C.HOT_GLOW,240)
        elif z._hovering:   bc2=qcol(C.BORDER_HOT,220)
        else:               bc2=qcol(C.BORDER,170)
        pen=QPen(bc2,1.6,Qt.PenStyle.DashLine); pen.setDashOffset(z._dash_offset)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush); p.drawRoundedRect(rect,6,6)

        # corner hex-style brackets
        bl=14; ca=qcol(C.PRI_DIM if not z._current_file else C.GREEN, 180)
        p.setPen(QPen(ca,1.8))
        for bx,by,dx,dy in [(pad,pad,1,1),(W-pad,pad,-1,1),(pad,H-pad,1,-1),(W-pad,H-pad,-1,-1)]:
            p.drawLine(int(bx),int(by),int(bx+dx*bl),int(by))
            p.drawLine(int(bx),int(by),int(bx),int(by+dy*bl))

        if z._current_file: self._paint_file(p,W,H)
        elif z._drag_over:  self._paint_drag_over(p,W,H)
        else:               self._paint_idle(p,W,H,z._hovering)

    def _paint_idle(self, p, W, H, hover):
        cx,cy=W/2,H/2
        col=qcol(C.PRI_DIM if not hover else C.PRI)
        p.setPen(QPen(col,2)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(cx,cy-14),QPointF(cx,cy+4))
        p.drawLine(QPointF(cx-8,cy-6),QPointF(cx,cy-14))
        p.drawLine(QPointF(cx+8,cy-6),QPointF(cx,cy-14))
        p.drawLine(QPointF(cx-14,cy+4),QPointF(cx+14,cy+4))
        p.setFont(QFont("Courier New",8))
        p.setPen(QPen(qcol(C.PRI_DIM if not hover else C.TEXT),1))
        p.drawText(QRectF(0,cy+8,W,16),Qt.AlignmentFlag.AlignCenter,"Drop file here  or  Click to Browse")
        p.setFont(QFont("Courier New",7))
        p.setPen(QPen(qcol("#1a4a5a"),1))
        p.drawText(QRectF(0,cy+24,W,14),Qt.AlignmentFlag.AlignCenter,"Images · Video · Audio · PDF · Docs · Code · Data")

    def _paint_drag_over(self, p, W, H):
        cx,cy=W/2,H/2
        p.setFont(QFont("Courier New",20)); p.setPen(QPen(qcol(C.HOT_GLOW),1))
        p.drawText(QRectF(0,cy-24,W,32),Qt.AlignmentFlag.AlignCenter,"⬇")
        p.setFont(QFont("Courier New",8,QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.PRI),1))
        p.drawText(QRectF(0,cy+12,W,16),Qt.AlignmentFlag.AlignCenter,"Release to load")

    def _paint_file(self, p, W, H):
        path=Path(self._z._current_file); cat=_file_category(path)
        icon,icon_col=_FILE_ICONS.get(cat,_FILE_ICONS["unknown"])
        size_str=_fmt_size(path.stat().st_size); ext_str=path.suffix.upper().lstrip("."or"FILE")
        block_x,block_w=10,64
        p.setFont(QFont("Segoe UI Emoji",22) if _OS=="Windows" else QFont("Arial",22))
        p.setPen(QPen(qcol(icon_col),1))
        p.drawText(QRectF(block_x,0,block_w,H),Qt.AlignmentFlag.AlignCenter,icon)
        tx=block_x+block_w+8; tw=W-tx-40
        p.setFont(QFont("Courier New",8,QFont.Weight.Bold)); p.setPen(QPen(qcol(C.WHITE),1))
        name=path.name if len(path.name)<=36 else path.name[:33]+"..."
        p.drawText(QRectF(tx,H*0.18,tw,16),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,name)
        p.setFont(QFont("Courier New",7)); p.setPen(QPen(qcol(C.TEXT_DIM),1))
        p.drawText(QRectF(tx,H*0.18+18,tw,14),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,f"{ext_str}  ·  {size_str}")
        p.setFont(QFont("Courier New",6)); p.setPen(QPen(qcol("#1e5c6a"),1))
        par=str(path.parent); par=("…"+par[-43:]) if len(par)>44 else par
        p.drawText(QRectF(tx,H*0.18+34,tw,12),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,par)
        p.setFont(QFont("Courier New",9,QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.RED,200),1))
        p.drawText(QRectF(W-36,0,30,H),Qt.AlignmentFlag.AlignCenter,"✕")

    def mousePressEvent(self, e):
        z=self._z
        if z._current_file and e.pos().x()>self.width()-36: z.clear_file()
        else: z.mousePressEvent(e)


# ═══════════════════════════════════════════════════════════════════════════════
#  SETUP OVERLAY
# ═══════════════════════════════════════════════════════════════════════════════
class SetupOverlay(QWidget):
    done = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            SetupOverlay {{
                background: rgba(0,5,12,252);
                border: 1px solid {C.BORDER_HOT};
                border-radius: 8px;
            }}
        """)
        detected = {"darwin":"mac","windows":"windows"}.get(_OS.lower(),"linux")
        self._sel_os = detected
        layout = QVBoxLayout(self); layout.setContentsMargins(34,26,34,26); layout.setSpacing(9)

        def _lbl(txt,fs=9,bold=False,color=C.PRI,align=Qt.AlignmentFlag.AlignCenter):
            w=QLabel(txt); w.setAlignment(align)
            w.setFont(QFont("Courier New",fs,QFont.Weight.Bold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color:{color};background:transparent;"); return w

        layout.addWidget(_lbl("◈  INITIALISATION REQUIRED",13,True))
        layout.addWidget(_lbl("Configure J.A.R.V.I.S. before first boot.",9,color=C.PRI_DIM))
        layout.addSpacing(6)
        sep=QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{C.BORDER_A};"); layout.addWidget(sep)
        layout.addSpacing(4)
        layout.addWidget(_lbl("GEMINI API KEY",8,color=C.TEXT_DIM,align=Qt.AlignmentFlag.AlignLeft))
        self._key_input=QLineEdit(); self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setPlaceholderText("AIza…")
        self._key_input.setFont(QFont("Courier New",10)); self._key_input.setFixedHeight(34)
        self._key_input.setStyleSheet(f"""
            QLineEdit{{background:{C.DARK};color:{C.TEXT};border:1px solid {C.BORDER_A};border-radius:4px;padding:4px 10px;}}
            QLineEdit:focus{{border:1px solid {C.PRI};}}""")
        layout.addWidget(self._key_input); layout.addSpacing(12)
        sep2=QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color:{C.BORDER_A};"); layout.addWidget(sep2)
        layout.addSpacing(4)
        layout.addWidget(_lbl("OPERATING SYSTEM",8,color=C.TEXT_DIM,align=Qt.AlignmentFlag.AlignLeft))
        det_name={"windows":"Windows","mac":"macOS","linux":"Linux"}[detected]
        layout.addWidget(_lbl(f"Auto-detected: {det_name}",8,color=C.GOLD,align=Qt.AlignmentFlag.AlignLeft))
        os_row=QHBoxLayout(); os_row.setSpacing(8)
        self._os_btns: dict[str,QPushButton]={}
        for key,label in [("windows","⊞  Windows"),("mac","  macOS"),("linux","🐧  Linux")]:
            btn=QPushButton(label); btn.setFont(QFont("Courier New",9,QFont.Weight.Bold))
            btn.setFixedHeight(34); btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _,k=key: self._sel(k))
            os_row.addWidget(btn); self._os_btns[key]=btn
        layout.addLayout(os_row); self._sel(detected); layout.addSpacing(12)
        init_btn=QPushButton("▸  INITIALISE SYSTEMS")
        init_btn.setFont(QFont("Courier New",10,QFont.Weight.Bold))
        init_btn.setFixedHeight(38); init_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        init_btn.setStyleSheet(f"""
            QPushButton{{background:transparent;color:{C.PRI};border:1px solid {C.PRI_DIM};border-radius:4px;letter-spacing:2px;}}
            QPushButton:hover{{background:{C.PRI_GHO};border:1px solid {C.PRI};color:{C.PRI_BRIGHT};}}""")
        init_btn.clicked.connect(self._submit); layout.addWidget(init_btn)

    def _sel(self, key):
        self._sel_os=key
        pal={"windows":(C.PRI,"#001a22"),"mac":(C.GOLD,"#1a1400"),"linux":(C.GREEN,"#001a0d")}
        for k,btn in self._os_btns.items():
            if k==key:
                fg,bg=pal[k]
                btn.setStyleSheet(f"QPushButton{{background:{fg};color:{bg};border:none;border-radius:4px;font-weight:bold;}}")
            else:
                btn.setStyleSheet(f"""QPushButton{{background:{C.DARK};color:{C.TEXT_DIM};border:1px solid {C.BORDER};border-radius:4px;}}
                    QPushButton:hover{{color:{C.TEXT};border:1px solid {C.BORDER_HOT};}}""")

    def _submit(self):
        key=self._key_input.text().strip()
        if not key:
            self._key_input.setStyleSheet(self._key_input.styleSheet()+f" QLineEdit{{border:1px solid {C.RED};}}")
            return
        self.done.emit(key,self._sel_os)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION HEADER WIDGET
# ═══════════════════════════════════════════════════════════════════════════════
class _SecHeader(QWidget):
    """Stark-tech section label with animated side lines."""
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self._text = text; self._tick = 0
        self.setFixedHeight(20)
        t = QTimer(self); t.timeout.connect(self._anim); t.start(80)

    def _anim(self): self._tick += 1; self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W,H = self.width(),self.height(); cy=H/2
        p.setFont(QFont("Courier New",7,QFont.Weight.Bold))
        fm = p.fontMetrics(); tw = fm.horizontalAdvance(f"▸ {self._text}")
        # left line
        ll = (W - tw) // 2 - 10
        if ll > 0:
            g=QLinearGradient(0,cy,ll,cy); g.setColorAt(0,QColor(0,0,0,0))
            g.setColorAt(1,QColor(C.PRI_DIM))
            p.setPen(QPen(QBrush(g),1))
            p.drawLine(QPointF(0,cy),QPointF(ll,cy))
        # text
        p.setPen(QPen(qcol(C.TEXT_MED),1))
        p.drawText(QRectF(0,0,W,H),Qt.AlignmentFlag.AlignCenter,f"▸ {self._text}")
        # right line
        rx = (W+tw)//2+10
        if rx < W:
            g2=QLinearGradient(rx,cy,W,cy); g2.setColorAt(0,QColor(C.PRI_DIM))
            g2.setColorAt(1,QColor(0,0,0,0))
            p.setPen(QPen(QBrush(g2),1))
            p.drawLine(QPointF(rx,cy),QPointF(W,cy))
        # moving dot
        dot_x = (ll + int((W//2 - ll) * ((math.sin(self._tick*0.12)+1)/2))) if ll > 0 else 0
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(qcol(C.PRI_BRIGHT, 140)))
        p.drawEllipse(QPointF(dot_x,cy),2.5,2.5)


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ═══════════════════════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    _log_sig   = pyqtSignal(str)
    _state_sig = pyqtSignal(str)

    def __init__(self, face_path: str):
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S — CodeCrafters")
        self.setMinimumSize(_MIN_W, _MIN_H)
        self.resize(_DEFAULT_W, _DEFAULT_H)
        screen = QApplication.primaryScreen().availableGeometry()
        self.move((screen.width()-_DEFAULT_W)//2,(screen.height()-_DEFAULT_H)//2)

        self.on_text_command = None
        self._muted = False
        self._current_file: str | None = None

        central = QWidget()
        central.setStyleSheet(f"background:{C.BG};")
        self.setCentralWidget(central)
        root = QVBoxLayout(central); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        root.addWidget(self._build_header())

        body = QHBoxLayout(); body.setContentsMargins(0,0,0,0); body.setSpacing(0)
        self._left_panel = self._build_left_panel(); body.addWidget(self._left_panel,stretch=0)
        self.hud = HudCanvas(face_path)
        self.hud.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
        body.addWidget(self.hud,stretch=5)
        self._right_panel = self._build_right_panel(); body.addWidget(self._right_panel,stretch=0)

        root.addLayout(body,stretch=1)
        root.addWidget(self._build_footer())

        self._clock_tmr = QTimer(self); self._clock_tmr.timeout.connect(self._tick_clock)
        self._clock_tmr.start(1000); self._tick_clock()

        self._metric_tmr = QTimer(self); self._metric_tmr.timeout.connect(self._update_metrics)
        self._metric_tmr.start(2000); self._update_metrics()

        self._log_sig.connect(self._log.append_log)
        self._state_sig.connect(self._apply_state)

        self._overlay: SetupOverlay | None = None
        self._ready = self._check_config()
        if not self._ready: self._show_setup()

        sc_mute = QShortcut(QKeySequence("F4"),self); sc_mute.activated.connect(self._toggle_mute)
        sc_full = QShortcut(QKeySequence("F11"),self); sc_full.activated.connect(self._toggle_fullscreen)

    def _toggle_fullscreen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._overlay and self._overlay.isVisible():
            ow,oh=500,420; cw=self.centralWidget()
            self._overlay.setGeometry((cw.width()-ow)//2,(cw.height()-oh)//2,ow,oh)

    def _update_metrics(self):
        snap = _metrics.snapshot()
        cpu=snap["cpu"]; self._bar_cpu.set_value(cpu,f"{cpu:.0f}%")
        mem=snap["mem"]; self._bar_mem.set_value(mem,f"{mem:.0f}%")
        net=snap["net"]
        self._bar_net.set_value(min(100,net*10),(f"{net*1024:.0f}KB/s" if net<1 else f"{net:.1f}MB/s"))
        gpu=snap["gpu"]
        self._bar_gpu.set_value(gpu,f"{gpu:.0f}%") if gpu>=0 else self._bar_gpu.set_value(0,"N/A")
        tmp=snap["tmp"]
        self._bar_tmp.set_value(min(100,tmp),f"{tmp:.0f}°C") if tmp>=0 else self._bar_tmp.set_value(0,"N/A")
        try:
            e=time.time()-psutil.boot_time(); h=int(e//3600); m=int((e%3600)//60)
            self._uptime_lbl.setText(f"UP  {h:02d}:{m:02d}")
        except Exception: self._uptime_lbl.setText("UP  --:--")
        try: self._proc_lbl.setText(f"PROC  {len(psutil.pids())}")
        except Exception: self._proc_lbl.setText("PROC  --")

    # ── HEADER ────────────────────────────────────────────────────────────────
    def _build_header(self) -> QWidget:
        w = QWidget(); w.setFixedHeight(64)
        w.setStyleSheet(
            f"background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 {C.DARK},stop:0.3 #00090f,stop:0.5 #000c18,stop:0.7 #00090f,stop:1 {C.DARK});"
            f"border-bottom:2px solid {C.BORDER_HOT};")
        lay = QHBoxLayout(w); lay.setContentsMargins(20,0,20,0)

        def _badge(txt, color=C.TEXT_MED, fs=7):
            l=QLabel(txt); l.setFont(QFont("Courier New",fs))
            l.setStyleSheet(f"color:{color};background:transparent;"); return l

        left_col=QVBoxLayout(); left_col.setSpacing(2)
        left_col.addWidget(_badge("J.A.R.V.I.S",C.PRI_DIM,8))
        left_col.addWidget(_badge("STARK INDUSTRIES",C.HOT_DIM,6))
        lay.addLayout(left_col); lay.addStretch()

        mid=QVBoxLayout(); mid.setSpacing(3)
        title=QLabel("J.A.R.V.I.S")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Courier New",20,QFont.Weight.Bold))
        title.setStyleSheet(f"color:{C.PRI};background:transparent;letter-spacing:8px;")
        mid.addWidget(title)
        sub=QLabel("Made to Automate Computation To Make it Easier and Productive")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setFont(QFont("Courier New",7)); sub.setStyleSheet(f"color:{C.PRI_DIM};background:transparent;")
        mid.addWidget(sub)
        lay.addLayout(mid); lay.addStretch()

        right_col=QVBoxLayout(); right_col.setSpacing(2)
        self._clock_lbl=QLabel("00:00:00")
        self._clock_lbl.setFont(QFont("Courier New",16,QFont.Weight.Bold))
        self._clock_lbl.setStyleSheet(f"color:{C.PRI};background:transparent;")
        self._clock_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._clock_lbl)
        self._date_lbl=QLabel("")
        self._date_lbl.setFont(QFont("Courier New",7))
        self._date_lbl.setStyleSheet(f"color:{C.TEXT_DIM};background:transparent;")
        self._date_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._date_lbl)
        lay.addLayout(right_col)
        return w

    def _tick_clock(self):
        self._clock_lbl.setText(time.strftime("%H:%M:%S"))
        self._date_lbl.setText(time.strftime("%a %d %b %Y"))

    # ── LEFT PANEL ────────────────────────────────────────────────────────────
    def _build_left_panel(self) -> QWidget:
        w=QWidget(); w.setFixedWidth(_LEFT_W)
        w.setStyleSheet(
            f"background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 {C.DARK},stop:1 #000c18);"
            f"border-right:1px solid {C.BORDER_A};")
        lay=QVBoxLayout(w); lay.setContentsMargins(10,14,10,14); lay.setSpacing(7)

        hdr=QLabel("◈ SYS CONFIGURATIONS")
        hdr.setFont(QFont("Courier New",7,QFont.Weight.Bold))
        hdr.setStyleSheet(f"color:{C.PRI};background:transparent;border-bottom:1px solid {C.BORDER_A};padding-bottom:5px;")
        lay.addWidget(hdr); lay.addSpacing(2)

        self._bar_cpu=MetricBar("CPU",C.PRI)
        self._bar_mem=MetricBar("MEM",C.GOLD)
        self._bar_net=MetricBar("NET",C.GREEN)
        self._bar_gpu=MetricBar("GPU",C.HOT)
        self._bar_tmp=MetricBar("TMP","#ff6688")
        for bar in [self._bar_cpu,self._bar_mem,self._bar_net,self._bar_gpu,self._bar_tmp]:
            lay.addWidget(bar)

        lay.addSpacing(8)
        ip=QWidget()
        ip.setStyleSheet(f"background:{C.PANEL2};border:1px solid {C.BORDER_A};border-radius:5px;")
        ipl=QVBoxLayout(ip); ipl.setContentsMargins(8,6,8,6); ipl.setSpacing(5)
        self._uptime_lbl=QLabel("UP  --:--")
        self._uptime_lbl.setFont(QFont("Courier New",8,QFont.Weight.Bold))
        self._uptime_lbl.setStyleSheet(f"color:{C.GREEN};background:transparent;border:none;")
        ipl.addWidget(self._uptime_lbl)
        self._proc_lbl=QLabel("PROC  --")
        self._proc_lbl.setFont(QFont("Courier New",8))
        self._proc_lbl.setStyleSheet(f"color:{C.TEXT_MED};background:transparent;border:none;")
        ipl.addWidget(self._proc_lbl)
        os_name={"Windows":"WIN","Darwin":"macOS","Linux":"LINUX"}.get(_OS,_OS.upper())
        osl=QLabel(f"OS  {os_name}"); osl.setFont(QFont("Courier New",8))
        osl.setStyleSheet(f"color:{C.GOLD};background:transparent;border:none;")
        ipl.addWidget(osl); lay.addWidget(ip)

        lay.addStretch()

        for txt,col,bg in [("AI CORE\nACTIVE",C.GREEN,"#001608"),("SEC\nCLEARED",C.PRI,"#001020")]:
            lbl=QLabel(txt); lbl.setFont(QFont("Courier New",7,QFont.Weight.Bold))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color:{col};background:{bg};border:1px solid {col};border-radius:4px;padding:5px;")
            lay.addWidget(lbl)
        return w

    # ── RIGHT PANEL ───────────────────────────────────────────────────────────
    def _build_right_panel(self) -> QWidget:
        w=QWidget(); w.setFixedWidth(_RIGHT_W)
        w.setStyleSheet(
            f"background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 #000c18,stop:1 {C.DARK});"
            f"border-left:1px solid {C.BORDER_A};")
        lay=QVBoxLayout(w); lay.setContentsMargins(10,10,10,10); lay.setSpacing(6)

        lay.addWidget(_SecHeader("ACTIVITY LOG"))
        self._log=LogWidget(); lay.addWidget(self._log,stretch=1)

        sep=QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{C.BORDER_A};margin:3px 0;"); lay.addWidget(sep)

        lay.addWidget(_SecHeader("FILE UPLOAD"))
        self._drop_zone=FileDropZone()
        self._drop_zone.file_selected.connect(self._on_file_selected)
        lay.addWidget(self._drop_zone)

        self._file_hint=QLabel("No file loaded — drop or click above to upload")
        self._file_hint.setFont(QFont("Courier New",7))
        self._file_hint.setStyleSheet(f"color:{C.TEXT_MED};background:transparent;")
        self._file_hint.setWordWrap(True); lay.addWidget(self._file_hint)

        sep2=QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color:{C.BORDER_A};margin:2px 0;"); lay.addWidget(sep2)

        lay.addWidget(_SecHeader("COMMAND INPUT"))
        lay.addLayout(self._build_input_row())

        self._mute_btn=QPushButton("🎙  MICROPHONE ACTIVE")
        self._mute_btn.setFixedHeight(34)
        self._mute_btn.setFont(QFont("Courier New",8,QFont.Weight.Bold))
        self._mute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mute_btn.clicked.connect(self._toggle_mute)
        self._style_mute_btn(); lay.addWidget(self._mute_btn)

        fs_btn=QPushButton("⛶  FULLSCREEN  [F11]")
        fs_btn.setFixedHeight(28); fs_btn.setFont(QFont("Courier New",7))
        fs_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        fs_btn.setStyleSheet(f"""
            QPushButton{{background:transparent;color:{C.TEXT_MED};border:1px solid {C.BORDER};border-radius:4px;}}
            QPushButton:hover{{color:{C.PRI};border:1px solid {C.BORDER_HOT};background:{C.PRI_GHO};}}""")
        fs_btn.clicked.connect(self._toggle_fullscreen); lay.addWidget(fs_btn)
        return w

    def _build_input_row(self) -> QHBoxLayout:
        row=QHBoxLayout(); row.setSpacing(6)
        self._input=QLineEdit()
        self._input.setPlaceholderText("Type a command or question…")
        self._input.setFont(QFont("Courier New",9))
        self._input.setFixedHeight(36)
        self._input.setStyleSheet(f"""
            QLineEdit{{background:{C.DARK};color:{C.WHITE};border:1px solid {C.BORDER_A};border-radius:4px;padding:4px 12px;}}
            QLineEdit:focus{{border:1px solid {C.PRI};color:{C.PRI_FLARE};}}""")
        self._input.returnPressed.connect(self._send); row.addWidget(self._input)

        send=QPushButton("▸"); send.setFixedSize(36,36)
        send.setFont(QFont("Courier New",13,QFont.Weight.Bold))
        send.setCursor(Qt.CursorShape.PointingHandCursor)
        send.setStyleSheet(f"""
            QPushButton{{background:{C.PANEL};color:{C.PRI};border:1px solid {C.PRI_DIM};border-radius:4px;}}
            QPushButton:hover{{background:{C.PRI_GHO};border:1px solid {C.PRI};color:{C.PRI_BRIGHT};}}""")
        send.clicked.connect(self._send); row.addWidget(send)
        return row

    # ── FOOTER ────────────────────────────────────────────────────────────────
    def _build_footer(self) -> QWidget:
        w=QWidget(); w.setFixedHeight(26)
        w.setStyleSheet(f"background:{C.DARK};border-top:1px solid {C.BORDER_A};")
        lay=QHBoxLayout(w); lay.setContentsMargins(18,0,18,0)
        def _fl(txt,color=C.TEXT_MED):
            l=QLabel(txt); l.setFont(QFont("Courier New",7))
            l.setStyleSheet(f"color:{color};background:transparent;"); return l
        lay.addWidget(_fl("[F4] Mute  ·  [F11] Fullscreen"))
        lay.addStretch()
        lay.addWidget(_fl("Made By CodeCrafters SOURADIPTA PATRA  ·  J.A.R.V.I.S ·  CLASSIFIED"))
        lay.addStretch()
        lay.addWidget(_fl("© 2026 CodeCrafters",C.PRI_DIM))
        return w

    # ── HANDLERS ──────────────────────────────────────────────────────────────
    def _on_file_selected(self, path: str):
        self._current_file=path; p2=Path(path); cat=_file_category(p2)
        icon,_=_FILE_ICONS.get(cat,_FILE_ICONS["unknown"]); size=_fmt_size(p2.stat().st_size)
        self._file_hint.setText(f"{icon}  {p2.name}  ·  {size}  ·  Tell JARVIS what to do with it")
        self._log.append_log(f"FILE: {p2.name} ({size}) loaded")
        if self.on_text_command:
            msg=(f"[FILE_UPLOADED] path={path} | name={p2.name} | type={p2.suffix.lstrip('.')} | size={size} | "
                 f"Briefly tell the user you can see the file '{p2.name}' ({size}) has been uploaded and ask what they'd like to do with it.")
            threading.Thread(target=self.on_text_command,args=(msg,),daemon=True).start()

    def _toggle_mute(self):
        self._muted=not self._muted; self.hud.muted=self._muted; self._style_mute_btn()
        if self._muted: self._apply_state("MUTED"); self._log.append_log("SYS: Microphone muted.")
        else: self._apply_state("LISTENING"); self._log.append_log("SYS: Microphone active.")

    def _style_mute_btn(self):
        if self._muted:
            self._mute_btn.setText("🔇  MICROPHONE MUTED")
            self._mute_btn.setStyleSheet(f"""QPushButton{{background:#180010;color:{C.MUTED_C};border:1px solid {C.MUTED_C};border-radius:4px;}}
                QPushButton:hover{{background:#240018;}}""")
        else:
            self._mute_btn.setText("🎙  MICROPHONE ACTIVE")
            self._mute_btn.setStyleSheet(f"""QPushButton{{background:#001808;color:{C.GREEN};border:1px solid {C.GREEN};border-radius:4px;}}
                QPushButton:hover{{background:#00240c;}}""")

    def _send(self):
        txt=self._input.text().strip()
        if not txt: return
        self._input.clear(); self._log.append_log(f"You: {txt}")
        if self.on_text_command:
            threading.Thread(target=self.on_text_command,args=(txt,),daemon=True).start()

    def _apply_state(self, state: str):
        self.hud.state=state; self.hud.speaking=(state=="SPEAKING")

    def _check_config(self) -> bool:
        if not API_FILE.exists(): return False
        try:
            d=json.loads(API_FILE.read_text(encoding="utf-8"))
            return bool(d.get("gemini_api_key")) and bool(d.get("os_system"))
        except Exception: return False

    def _show_setup(self):
        ov=SetupOverlay(self.centralWidget()); cw=self.centralWidget(); ow,oh=500,420
        ov.setGeometry((cw.width()-ow)//2,(cw.height()-oh)//2,ow,oh)
        ov.done.connect(self._on_setup_done); ov.show(); self._overlay=ov

    def _on_setup_done(self, key: str, os_name: str):
        os.makedirs(CONFIG_DIR,exist_ok=True)
        API_FILE.write_text(json.dumps({"gemini_api_key":key,"os_system":os_name},indent=4),encoding="utf-8")
        self._ready=True
        if self._overlay: self._overlay.hide(); self._overlay=None
        self._apply_state("LISTENING")
        self._log.append_log(f"SYS: Initialised. OS={os_name.upper()}. JARVIS online.")


# ═══════════════════════════════════════════════════════════════════════════════
#  PUBLIC API (identical surface to original)
# ═══════════════════════════════════════════════════════════════════════════════
class _RootShim:
    def __init__(self, app): self._app=app
    def mainloop(self): self._app.exec()
    def protocol(self,*_): pass


class JarvisUI:
    def __init__(self, face_path: str, size=None):
        self._app=QApplication.instance() or QApplication(sys.argv)
        self._app.setStyle("Fusion"); self._win=MainWindow(face_path); self._win.show()
        self.root=_RootShim(self._app)

    @property
    def muted(self) -> bool: return self._win._muted
    @muted.setter
    def muted(self, v: bool):
        if v!=self._win._muted: self._win._toggle_mute()

    @property
    def current_file(self) -> str | None: return self._win._drop_zone.current_file()

    @property
    def on_text_command(self): return self._win.on_text_command
    @on_text_command.setter
    def on_text_command(self, cb): self._win.on_text_command=cb

    def set_state(self, state: str): self._win._state_sig.emit(state)
    def write_log(self, text: str): self._win._log_sig.emit(text)
    def wait_for_api_key(self):
        while not self._win._ready: time.sleep(0.1)
    def start_speaking(self): self.set_state("SPEAKING")
    def stop_speaking(self):
        if not self.muted: self.set_state("LISTENING")
