# serial_mon

A simple, clean serial terminal for Linux (and macOS). No IDE, no bloat — just a port, a baud rate, a receive window, and a send line. Exactly like the Arduino serial monitor, but living in your terminal.

![Python](https://img.shields.io/badge/python-3.6%2B-blue) ![License](https://img.shields.io/badge/license-MIT-green)

---

## What it is

`serial_mon.py` is a single-file Python script that gives you a split-pane UART terminal:

- **Top pane** — live scrolling receive window
- **Bottom line** — persistent send input, always ready

That's it. No project files, no configuration GUIs, no installation wizard. Run it, pick your port, and you're talking to your device.

---

## Requirements

- Python 3.6+
- `pyserial`

Install the dependency:

```bash
pip3 install pyserial --user
```

---

## Usage

```bash
python3 serial_mon.py
```

Or skip the wizard for a specific port/baud:

```bash
python3 serial_mon.py --port /dev/ttyUSB0 --baud 9600
```

### Startup wizard

On launch, the wizard will:

1. Show all detected serial ports
2. Ask which port to connect to (enter a number, or type the path directly, or `r` to refresh the list)
3. Show your last used config (port, baud, format, line ending) and ask if you want to use it — just press **Enter** to connect immediately, or `n` to change settings

After the first run, your settings are saved to `serial_mon.cfg` in the same directory. Every subsequent launch remembers exactly where you left off.

### Keyboard shortcuts (inside the terminal)

| Key | Action |
|---|---|
| `Enter` | Send typed text |
| `Backspace` | Delete last character |
| `Ctrl+H` *(empty buffer)* | Toggle HEX / ASCII display |
| `Ctrl+L` | Clear the receive window |
| `Ctrl+R` | Return to configuration wizard |
| `PgUp / PgDn` | Scroll through receive history |
| `End` | Jump back to live (bottom) |
| `Ctrl+C` | Quit |

### Display modes

- **ASCII** (default) — received bytes shown as readable text
- **HEX** — each byte shown as a two-digit hex value, useful for debugging binary protocols

Switch between them with `Ctrl+H` while the send buffer is empty.

### Line endings

When you send a message, `serial_mon` can automatically append a line ending. Options:

| Option | Bytes sent |
|---|---|
| None | (nothing appended) |
| LF *(default)* | `0x0A` |
| CR | `0x0D` |
| CR+LF | `0x0D 0x0A` |

---

## Configuration file

`serial_mon.cfg` is created automatically in the same directory as the script after your first run. It is a plain text file and can be edited by hand:

```
# serial_mon saved configuration
port     = /dev/ttyUSB0
baud     = 115200
bytesize = 8
parity   = N
stopbits = 1
newline  = \n
```

---

## Optional: run it as a terminal command

If you want to type `serialterm` from anywhere in your terminal instead of navigating to the script each time, here are two ways to do it.

**Linux (bash):**

```bash
nano ~/.bashrc
```

Scroll to the bottom and add:

```bash
alias serialterm='python3 /path/to/serial_mon.py'
```

Reload your shell:

```bash
source ~/.bashrc
```

**macOS (zsh, default since macOS Catalina):**

```bash
nano ~/.zshrc
```

Add the same alias line, then reload:

```bash
source ~/.zshrc
```

Now `serialterm` works from any directory.

---

### Windows

`serial_mon.py` uses the `curses` library, which is not natively available on Windows. The easiest path is to use **WSL (Windows Subsystem for Linux)**, which gives you a full Linux environment. Once WSL is set up, follow the Linux instructions above exactly.

---

## Format presets

| Preset | Data bits | Parity | Stop bits |
|---|---|---|---|
| 8N1 *(default)* | 8 | None | 1 |
| 8N2 | 8 | None | 2 |
| 8E1 | 8 | Even | 1 |
| 8O1 | 8 | Odd | 1 |
| 7E1 | 7 | Even | 1 |
| 7O1 | 7 | Odd | 1 |

---

## License

MIT
