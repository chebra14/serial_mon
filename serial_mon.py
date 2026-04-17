#!/usr/bin/env python3
"""
serial_mon.py — A clean UART terminal for Linux
Usage: python3 serial_mon.py [--port /dev/ttyUSB0] [--baud 115200]
Requires: pip install pyserial --break-system-packages
"""

import curses
import curses.textpad
import serial
import serial.tools.list_ports
import threading
import time
import sys
import argparse
import os

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_BAUD     = 115200
DEFAULT_BYTESIZE = 8
DEFAULT_PARITY   = 'N'
DEFAULT_STOPBITS = 1
DEFAULT_NEWLINE  = '\n'   # LF

PRESETS = {
    "8N1": (8, 'N', 1),
    "8N2": (8, 'N', 2),
    "8E1": (8, 'E', 1),
    "8O1": (8, 'O', 1),
    "7E1": (7, 'E', 1),
    "7O1": (7, 'O', 1),
}

BAUD_RATES = [300, 1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]

NEWLINE_OPTIONS = {
    "None":   "",
    "LF":     "\n",
    "CR":     "\r",
    "CR+LF":  "\r\n",
}

# ── Colour palette IDs ─────────────────────────────────────────────────────────
C_RX       = 1   # received data
C_TX       = 2   # echo of sent data
C_STATUS   = 3   # status / info bar
C_BORDER   = 4   # box borders
C_HEADER   = 5   # header bar
C_HEX      = 6   # hex overlay
C_PROMPT   = 7   # send-line prompt char
C_DIM      = 8   # muted text
C_ACCENT   = 9   # highlight / accent

def init_colors():
    curses.start_color()
    curses.use_default_colors()
    # dark bg = -1 (terminal default, usually near-black)
    curses.init_pair(C_RX,     curses.COLOR_GREEN,   -1)
    curses.init_pair(C_TX,     curses.COLOR_CYAN,    -1)
    curses.init_pair(C_STATUS, curses.COLOR_BLACK,   curses.COLOR_WHITE)
    curses.init_pair(C_BORDER, curses.COLOR_WHITE,   -1)
    curses.init_pair(C_HEADER, curses.COLOR_BLACK,   curses.COLOR_GREEN)
    curses.init_pair(C_HEX,    curses.COLOR_YELLOW,  -1)
    curses.init_pair(C_PROMPT, curses.COLOR_GREEN,   -1)
    curses.init_pair(C_DIM,    8,                    -1)   # dark grey
    curses.init_pair(C_ACCENT, curses.COLOR_WHITE,   -1)

# ── Setup wizard (runs before curses) ─────────────────────────────────────────
def list_ports():
    ports = sorted(serial.tools.list_ports.comports(), key=lambda p: p.device)
    return ports

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "serial_mon.cfg")

def load_config():
    """Load saved config from file, return dict or None if not found."""
    if not os.path.exists(CONFIG_FILE):
        return None
    cfg = {}
    try:
        with open(CONFIG_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    cfg[k.strip()] = v.strip()
        # parse types
        cfg["baud"]     = int(cfg.get("baud", DEFAULT_BAUD))
        cfg["bytesize"] = int(cfg.get("bytesize", DEFAULT_BYTESIZE))
        cfg["stopbits"] = int(cfg.get("stopbits", DEFAULT_STOPBITS))
        cfg["parity"]   = cfg.get("parity", DEFAULT_PARITY)
        cfg["newline"]  = cfg.get("newline", DEFAULT_NEWLINE).encode().decode("unicode_escape")
        cfg["port"]     = cfg.get("port", "")
        cfg["hex_mode"] = False
        return cfg
    except Exception:
        return None

def save_config(cfg):
    """Save current config to file."""
    try:
        with open(CONFIG_FILE, "w") as f:
            f.write("# serial_mon saved configuration\n")
            f.write(f"port     = {cfg['port']}\n")
            f.write(f"baud     = {cfg['baud']}\n")
            f.write(f"bytesize = {cfg['bytesize']}\n")
            f.write(f"parity   = {cfg['parity']}\n")
            f.write(f"stopbits = {cfg['stopbits']}\n")
            f.write(f"newline  = {cfg['newline'].encode('unicode_escape').decode()}\n")
    except Exception:
        pass

def setup_wizard(cli_port=None, cli_baud=None):
    """Interactive text-mode wizard. Returns config dict."""

    os.system("clear")
    banner = r"""
  ┌─────────────────────────────────────────┐
  │  ░░  serial_mon  ░░  UART terminal      │
  └─────────────────────────────────────────┘
"""
    print(banner)

    # ── Port list (always shown) ───────────────────────────────────────────────
    def show_ports():
        ports = list_ports()
        if ports:
            print("  Available ports:\n")
            for i, p in enumerate(ports):
                print(f"  [{i+1}]  {p.device:<20} {p.description}")
        else:
            print("  No ports detected.")
        print()
        return ports

    ports = show_ports()

    # ── Load saved config (or fall back to hard-coded defaults) ───────────────
    saved = load_config()
    if saved:
        last_port    = saved["port"]
        last_baud    = saved["baud"]
        last_preset  = next((k for k, v in PRESETS.items()
                             if v == (saved["bytesize"], saved["parity"], saved["stopbits"])), "8N1")
        last_nl      = next((k for k, v in NEWLINE_OPTIONS.items()
                             if v == saved["newline"]), "LF")
    else:
        last_port    = ""
        last_baud    = DEFAULT_BAUD
        last_preset  = "8N1"
        last_nl      = "LF"

    # ── Single prompt: continue with last config? ─────────────────────────────
    if last_port:
        nl_label = next(k for k, v in NEWLINE_OPTIONS.items() if v == NEWLINE_OPTIONS.get(last_nl, "\n"))
        print(f"  Last used:  {last_port}  |  {last_baud} bps  |  {last_preset}  |  append: {last_nl}")
        prompt_text = "  Use last config? [Enter = yes / n = change / r = refresh ports]: "
    else:
        print(f"  Defaults:  {DEFAULT_BAUD} bps  |  8N1  |  append: LF")
        prompt_text = "  Use defaults? [Enter = yes / n = change / r = refresh ports]: "

    while True:
        choice = input(prompt_text).strip().lower()
        if choice == 'r':
            os.system("clear")
            print(banner)
            ports = show_ports()
            if last_port:
                print(f"  Last used:  {last_port}  |  {last_baud} bps  |  {last_preset}  |  append: {last_nl}")
            continue
        break

    if choice != 'n':
        # Use last/default config
        if saved and last_port:
            cfg = saved.copy()
            cfg["hex_mode"] = False
        else:
            cfg = {
                "port":     last_port or "/dev/ttyUSB0",
                "baud":     DEFAULT_BAUD,
                "bytesize": DEFAULT_BYTESIZE,
                "parity":   DEFAULT_PARITY,
                "stopbits": DEFAULT_STOPBITS,
                "newline":  DEFAULT_NEWLINE,
                "hex_mode": False,
            }
        print(f"  → {cfg['port']}  {cfg['baud']} bps\n")
    else:
        cfg = {"hex_mode": False}
        print()

        # ── Port ──────────────────────────────────────────────────────────────
        if cli_port:
            cfg["port"] = cli_port
            print(f"  Port (from args): {cli_port}")
        else:
            default_port_hint = f"  Enter = {last_port}" if last_port else "  e.g. /dev/ttyUSB0"
            raw = input(f"  Port or number from list  [{default_port_hint}]: ").strip()
            while raw.lower() == 'r':
                os.system("clear")
                print(banner)
                ports = show_ports()
                raw = input(f"  Port or number from list  [{default_port_hint}]: ").strip()
            if raw == "" and last_port:
                cfg["port"] = last_port
            elif raw.isdigit() and 1 <= int(raw) <= len(ports):
                cfg["port"] = ports[int(raw) - 1].device
            else:
                cfg["port"] = raw or last_port or "/dev/ttyUSB0"
            print(f"  → Port: {cfg['port']}\n")

        # ── Baud rate ─────────────────────────────────────────────────────────
        if cli_baud:
            cfg["baud"] = cli_baud
            print(f"  Baud (from args): {cli_baud}")
        else:
            print(f"  Baud rate  [default: {last_baud}]")
            for i, b in enumerate(BAUD_RATES):
                marker = " ←" if b == last_baud else ""
                print(f"    {i+1:2}. {b}{marker}")
            raw = input(f"\n  Enter baud rate or number (Enter = {last_baud}): ").strip()
            if raw == "":
                cfg["baud"] = last_baud
            elif raw.isdigit() and 1 <= int(raw) <= len(BAUD_RATES):
                cfg["baud"] = BAUD_RATES[int(raw) - 1]
            else:
                try:
                    cfg["baud"] = int(raw)
                except ValueError:
                    cfg["baud"] = last_baud
            print(f"  → Baud: {cfg['baud']}\n")

        # ── Format preset ─────────────────────────────────────────────────────
        preset_keys = list(PRESETS.keys())
        print(f"  Format preset  [default: {last_preset}]")
        for i, k in enumerate(preset_keys):
            b, p, s = PRESETS[k]
            marker = " ←" if k == last_preset else ""
            print(f"    {i+1}. {k}  ({b} data bits, parity={p}, {s} stop bit){marker}")
        raw = input(f"\n  Choose preset (Enter = {last_preset}): ").strip()
        if raw == "":
            key = last_preset
        elif raw.isdigit() and 1 <= int(raw) <= len(preset_keys):
            key = preset_keys[int(raw) - 1]
        elif raw.upper() in PRESETS:
            key = raw.upper()
        else:
            key = last_preset
        cfg["bytesize"], cfg["parity"], cfg["stopbits"] = PRESETS[key]
        print(f"  → Format: {key}\n")

        # ── Line ending ───────────────────────────────────────────────────────
        nl_keys = list(NEWLINE_OPTIONS.keys())
        print(f"  Append on send  [default: {last_nl}]")
        for i, k in enumerate(nl_keys):
            val = NEWLINE_OPTIONS[k]
            marker = " ←" if k == last_nl else ""
            hex_repr = " ".join(f"0x{ord(c):02X}" for c in val) if val else "nothing"
            print(f"    {i+1}. {k:<8} ({hex_repr}){marker}")
        raw = input(f"\n  Choose line ending (Enter = {last_nl}): ").strip()
        if raw == "":
            cfg["newline"] = NEWLINE_OPTIONS[last_nl]
        elif raw.isdigit() and 1 <= int(raw) <= len(nl_keys):
            cfg["newline"] = NEWLINE_OPTIONS[nl_keys[int(raw) - 1]]
        else:
            cfg["newline"] = NEWLINE_OPTIONS.get(last_nl, DEFAULT_NEWLINE)
        chosen_nl = next(k for k, v in NEWLINE_OPTIONS.items() if v == cfg["newline"])
        print(f"  → Append: {chosen_nl}\n")

    save_config(cfg)
    print("  Starting terminal…\n")
    time.sleep(0.6)
    return cfg

# ── Curses TUI ─────────────────────────────────────────────────────────────────
class SerialMonitor:
    def __init__(self, stdscr, cfg):
        self.scr   = stdscr
        self.cfg   = cfg
        self.lines = []          # list of (text, color_pair, is_hex_line)
        self.lock  = threading.Lock()
        self.running  = True
        self.reconfigure = False
        self.hex_mode = cfg["hex_mode"]
        self.ser      = None
        self.send_buf = ""
        self.scroll_offset = 0   # lines from bottom (0 = live)
        self.status_msg = ""

        init_colors()
        curses.curs_set(1)
        self.scr.nodelay(True)

        self._connect()
        self._rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
        self._rx_thread.start()

    def _connect(self):
        try:
            self.ser = serial.Serial(
                port     = self.cfg["port"],
                baudrate = self.cfg["baud"],
                bytesize = self.cfg["bytesize"],
                parity   = self.cfg["parity"],
                stopbits = self.cfg["stopbits"],
                timeout  = 0.1,
            )
            self.status_msg = f"Connected  {self.cfg['port']}  {self.cfg['baud']}bps"
        except serial.SerialException as e:
            self.status_msg = f"ERROR: {e}"

    def _rx_loop(self):
        while self.running:
            if self.ser and self.ser.is_open:
                try:
                    data = self.ser.read(256)
                    if data:
                        self._ingest(data)
                except serial.SerialException:
                    self.status_msg = "Port disconnected"
                    break
            else:
                time.sleep(0.05)

    def _ingest(self, data: bytes):
        """Split incoming bytes into display lines."""
        try:
            text = data.decode("utf-8", errors="replace")
        except Exception:
            text = data.decode("latin-1", errors="replace")

        hex_str = " ".join(f"{b:02X}" for b in data)

        with self.lock:
            if self.hex_mode:
                self.lines.append((hex_str, C_HEX))
            else:
                # keep newlines as separators but show each chunk
                parts = text.split("\n")
                for i, part in enumerate(parts):
                    if part:
                        self.lines.append((part.rstrip("\r"), C_RX))
                    elif i < len(parts) - 1:
                        pass   # blank between split lines
            # cap buffer
            if len(self.lines) > 2000:
                self.lines = self.lines[-2000:]
            if self.scroll_offset == 0:
                pass  # stay at bottom

    def _send(self, text: str):
        if self.ser and self.ser.is_open:
            payload = (text + self.cfg["newline"]).encode("utf-8")
            self.ser.write(payload)
            with self.lock:
                echo = f"→ {text}"
                self.lines.append((echo, C_TX))

    def run(self):
        while self.running:
            self._draw()
            self._handle_input()
        if self.ser and self.ser.is_open:
            self.ser.close()

    def _draw(self):
        self.scr.erase()
        H, W = self.scr.getmaxyx()

        # ── Layout ───────────────────────────────────────────────────────────
        HEADER_H  = 2
        STATUS_H  = 1
        SEND_H    = 3
        RX_H      = H - HEADER_H - STATUS_H - SEND_H

        # ── Header ────────────────────────────────────────────────────────────
        header_win = self.scr.subwin(HEADER_H, W, 0, 0)
        header_win.bkgd(' ', curses.color_pair(C_HEADER) | curses.A_BOLD)
        title = f"  SERIAL MON  ░  {self.cfg['port']}  ░  {self.cfg['baud']} bps  ░  {'HEX' if self.hex_mode else 'ASCII'}  "
        keybinds = " [^H] hex  [^C] quit  [PgUp/Dn] scroll  [^L] clear "
        header_win.addstr(0, 0, title[:W], curses.color_pair(C_HEADER) | curses.A_BOLD)
        right_start = W - len(keybinds) - 1
        if right_start > len(title) and right_start > 0:
            header_win.addstr(0, right_start, keybinds[:W - right_start], curses.color_pair(C_HEADER))
        # thin separator line
        sep = "─" * W
        try:
            header_win.addstr(1, 0, sep[:W], curses.color_pair(C_BORDER))
        except curses.error:
            pass

        # ── RX pane ───────────────────────────────────────────────────────────
        rx_win = self.scr.subwin(RX_H, W, HEADER_H, 0)
        with self.lock:
            visible_lines = self.lines[:]

        total = len(visible_lines)
        # scroll offset: 0 = bottom
        max_scroll = max(0, total - RX_H)
        self.scroll_offset = min(self.scroll_offset, max_scroll)
        start_idx = max(0, total - RX_H - self.scroll_offset)
        display = visible_lines[start_idx: start_idx + RX_H]

        for row, (txt, cpair) in enumerate(display):
            # truncate safely
            safe = txt[:W - 1] if len(txt) >= W else txt
            try:
                rx_win.addstr(row, 0, safe, curses.color_pair(cpair))
            except curses.error:
                pass

        # scroll indicator
        if self.scroll_offset > 0:
            indicator = f" ↑ scrolled {self.scroll_offset} lines (PgDn → live) "
            try:
                rx_win.addstr(RX_H - 1, max(0, W - len(indicator) - 1),
                              indicator, curses.color_pair(C_STATUS))
            except curses.error:
                pass

        # ── Status bar ────────────────────────────────────────────────────────
        status_y = HEADER_H + RX_H
        status_win = self.scr.subwin(STATUS_H, W, status_y, 0)
        status_win.bkgd(' ', curses.color_pair(C_STATUS))
        nl_label = next((k for k, v in NEWLINE_OPTIONS.items() if v == self.cfg["newline"]), "?")
        right = f" append:{nl_label} "
        left  = f"  {self.status_msg}"
        try:
            status_win.addstr(0, 0, left[:W], curses.color_pair(C_STATUS))
            if len(left) + len(right) < W:
                status_win.addstr(0, W - len(right) - 1, right, curses.color_pair(C_STATUS))
        except curses.error:
            pass

        # ── Send pane ─────────────────────────────────────────────────────────
        send_y = status_y + STATUS_H
        send_win = self.scr.subwin(SEND_H, W, send_y, 0)
        border_line = "─" * W
        try:
            send_win.addstr(0, 0, border_line[:W], curses.color_pair(C_BORDER))
        except curses.error:
            pass
        prompt = "  › "
        try:
            send_win.addstr(1, 0, prompt, curses.color_pair(C_PROMPT) | curses.A_BOLD)
            buf_display = self.send_buf[-(W - len(prompt) - 1):]
            send_win.addstr(1, len(prompt), buf_display, curses.color_pair(C_ACCENT))
        except curses.error:
            pass
        hint = "  Enter=send  |  ^H (empty buf)=hex  |  ^L=clear  |  PgUp/Dn=scroll  |  ^R=config"
        try:
            send_win.addstr(2, 0, hint[:W], curses.color_pair(C_DIM))
        except curses.error:
            pass

        # cursor
        try:
            cursor_x = min(len(prompt) + len(self.send_buf[-(W - len(prompt) - 1):]), W - 1)
            self.scr.move(send_y + 1, cursor_x)
        except curses.error:
            pass

        self.scr.refresh()

    def _handle_input(self):
        try:
            key = self.scr.getch()
        except curses.error:
            return

        if key == -1:
            time.sleep(0.02)
            return

        H, W = self.scr.getmaxyx()
        RX_H = H - 2 - 1 - 3

        if key == 3:                        # Ctrl+C → quit
            self.running = False
        elif key == 8 or key == 127:        # Ctrl+H / Backspace (toggle hex when empty)
            if not self.send_buf:
                self.hex_mode = not self.hex_mode
                mode = "HEX" if self.hex_mode else "ASCII"
                self.status_msg = f"Display mode: {mode}"
            else:
                self.send_buf = self.send_buf[:-1]
        elif key == 12:                     # Ctrl+L → clear
            with self.lock:
                self.lines.clear()
            self.scroll_offset = 0
        elif key == curses.KEY_PPAGE:       # PgUp → scroll up
            self.scroll_offset = min(self.scroll_offset + RX_H // 2,
                                     max(0, len(self.lines) - RX_H))
        elif key == curses.KEY_NPAGE:       # PgDn → scroll down / back to live
            self.scroll_offset = max(0, self.scroll_offset - RX_H // 2)
        elif key == curses.KEY_END:
            self.scroll_offset = 0
        elif key in (10, 13):               # Enter → send
            if self.send_buf:
                self._send(self.send_buf)
                self.send_buf = ""
                self.scroll_offset = 0
        elif 32 <= key <= 126:              # printable
            self.send_buf += chr(key)
        elif key == 18:                     # Ctrl+R → back to config
            self.running = False
            self.reconfigure = True

# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="serial_mon — clean UART terminal")
    parser.add_argument("--port",  help="Serial port (skips wizard prompt)")
    parser.add_argument("--baud",  type=int, help="Baud rate (skips wizard prompt)")
    args = parser.parse_args()

    while True:
        try:
            cfg = setup_wizard(cli_port=args.port, cli_baud=args.baud)
        except KeyboardInterrupt:
            print("\n  Bye.")
            sys.exit(0)

        reconfig = [False]

        def _run(stdscr):
            mon = SerialMonitor(stdscr, cfg)
            mon.run()
            reconfig[0] = mon.reconfigure

        try:
            curses.wrapper(_run)
        except KeyboardInterrupt:
            pass

        if not reconfig[0]:
            break

    print("\n  serial_mon closed.\n")

if __name__ == "__main__":
    main()