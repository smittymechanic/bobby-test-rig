#!/usr/bin/env python3
"""Bobby Pi bridge — DRAFT v1, Thu 2026-11-19 (UNTESTED on the Pi).

What it is: the small program the Bobby Test Bench talks to over
Tailscale. The bench (on Muse's VM) reaches out to this Pi; this bridge
listens on TCP, runs each text command against the hardware wired to
the Pi, and sends one readback line back. Same command words the bench
app already uses, so nothing in the bench UI changes when the real
link lands: `EAR L FLAT`, `PAN -105`, `STATUS`, `HELP`, ...

Transport: plain TCP, one command per line, one reply line per command.
Binds 0.0.0.0:8765 by default — reachable ONLY over the Tailscale
tailnet (the Pi's LAN address 192.168.1.23 is behind Joshua's router
and nothing on the internet can reach it; no port forwarding).

STATUS OF THIS DRAFT — read before running:
- Written from the bench app's command vocabulary (bobby-test-bench
  server/src/actions.ts, Nov 19) and the proven hardware-PWM sweep
  (pi/ear-servo-sweep-hw-2026-11-18.py). NOT yet run on the Pi.
- Needs the Tailscale link up first: Pi on Tailscale, Muse's VM joined
  as `muse` and approved by Joshua. See
  ~/workspace/bobby-build/tailscale-pi-install-checklist-2026-11-19.md
- Needs `sudo` (for /sys/class/pwm) and `dtoverlay=pwm-2chan` in
  /boot/firmware/config.txt + reboot, same as the sweep script.

HARDWARE FITTED in v1 — and what is NOT:
- ONE ear servo, on GPIO18 (pin 12), hardware PWM, Adeept AD002,
  4.8-6 V ONLY from the 5 V phone charger (common ground to the Pi).
  The bench rig wires one servo at a time, so the bridge can only
  drive that one. WIRED_EAR below says which ear it is — CHANGE IT
  if the servo in the can right now is the other ear. Commands for
  the unwired ear answer NOT_FITTED, never a fake move.
- PAN, TILT, DRIVE, FACE/display, lobe LEDs, TEMP, VOLT: NOT fitted
  on the Pi bench yet (no ZOSKAY servos, no Ventuno, no sensors).
  They answer `ERR ... NOT_FITTED` honestly. Do NOT "fix" that by
  faking a move — the whole point of the bench is real readbacks.

Ear angles: bench degrees, 0..180. UP=0, FLAT=90, DROOP=150 (same
as the bench app). Servo value = deg/90 - 1; duty = 7.5 + value*2.5
at 50 Hz. Moves are smooth: 0.01 value (~0.9 deg) every 10 ms,
the step size that fixed the jitter on Nov 18.

RUN:
  sudo python3 pi/bobby_bridge.py            # listens on :8765
  sudo python3 pi/bobby_bridge.py --port 8765 --host 0.0.0.0
  python3 pi/bobby_bridge.py --self-test     # no hardware: parses
                                              # every command and prints
                                              # the replies it would send

TEST (from Muse's VM, once Tailscale is up):
  printf 'EAR L FLAT\\nSTATUS\\n' | nc <pi-tailscale-ip> 8765
"""

import argparse
import socket
import sys
from time import sleep

# --- Bench rig identity (edit here, not in the handlers) -------------------
WIRED_EAR = "L"        # <-- CHANGE to "R" if the servo in the can now is the RIGHT ear.
                       # The rig wires ONE ear servo at a time on GPIO18.
HW_PWM_GPIO = 18       # pin 12, dtoverlay=pwm-2chan (proven Nov 18)
HW_PWM_CHANNEL = 2     # GPIO18 with dtoverlay=pwm-2chan
PWM_HZ = 50
STEP = 0.01            # servo value per step (~0.9 deg); fine steps = smooth
DWELL_S = 0.01         # seconds per step (10 ms)

EAR_UP_DEG = 0
EAR_FLAT_DEG = 90
EAR_DROOP_DEG = 150

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8765


def duty_for(value: float) -> float:
    """Servo value (-1..1) -> duty-cycle percent at 50 Hz."""
    return 7.5 + value * 2.5


def deg_to_value(deg: float) -> float:
    """Bench degrees (0..180) -> servo value (-1..1)."""
    return deg / 90.0 - 1.0


class EarServo:
    """One AD002 on hardware PWM. Import of rpi_hardware_pwm is lazy so
    --self-test and HELP work on a machine with no Pi hardware."""

    def __init__(self) -> None:
        self.deg = 90.0  # assume flat at start; first move corrects it
        self._pwm = None

    def _ensure_pwm(self):
        if self._pwm is not None:
            return self._pwm
        from rpi_hardware_pwm import HardwarePWM

        last_error = None
        for chip in (2, 0):
            try:
                pwm = HardwarePWM(pwm_channel=HW_PWM_CHANNEL, hz=PWM_HZ, chip=chip)
                pwm.start(duty_for(deg_to_value(self.deg)))
                print(f"Hardware PWM live: pwmchip{chip}, channel {HW_PWM_CHANNEL} (GPIO{HW_PWM_GPIO}).", flush=True)
                self._pwm = pwm
                return pwm
            except Exception as e:  # noqa: BLE001 - try the other chip, then report
                last_error = e
                print(f"  pwmchip{chip} didn't work, trying the other...", flush=True)
        raise RuntimeError(
            "No hardware PWM channel found — is dtoverlay=pwm-2chan in "
            "/boot/firmware/config.txt, and did you reboot after adding it?"
        ) from last_error

    def move_to(self, target_deg: float) -> float:
        """Smooth move to target degrees; returns the degrees reached."""
        target_deg = max(0.0, min(180.0, target_deg))
        pwm = self._ensure_pwm()
        start = deg_to_value(self.deg)
        target = deg_to_value(target_deg)
        direction = 1 if target > start else -1
        v = start
        while (direction > 0 and v < target) or (direction < 0 and v > target):
            v = round(v + direction * STEP, 2)
            v = max(-1.0, min(1.0, v))
            pwm.change_duty_cycle(duty_for(v))
            sleep(DWELL_S)
        pwm.change_duty_cycle(duty_for(target))
        self.deg = target_deg
        return self.deg

    def stop(self) -> None:
        if self._pwm is not None:
            self._pwm.stop()
            self._pwm = None


class Bridge:
    """Command parser. `dry_run=True` never touches hardware — used by
    --self-test and by HELP on a non-Pi machine."""

    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self.ear = EarServo()

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def _fmt(v: float) -> str:
        return str(round(v * 10) / 10)

    def _ear_target(self, arg: str):
        if arg == "UP":
            return EAR_UP_DEG
        if arg == "FLAT":
            return EAR_FLAT_DEG
        if arg in ("DROOP", "DOWN"):
            return EAR_DROOP_DEG
        try:
            return max(0.0, min(180.0, float(arg)))
        except ValueError:
            return None

    def _do_ear(self, side: str, arg: str) -> str:
        target = self._ear_target(arg)
        if target is None:
            return f'ERR ear command needs UP | FLAT | DROOP | <deg> — got "EAR {side} {arg}"'
        if side == "BOTH":
            if self.dry_run:
                return (
                    f"WARN EAR {WIRED_EAR} → {self._fmt(target)}° (dry run, no hardware) · "
                    f"EAR {'R' if WIRED_EAR == 'L' else 'L'} NOT_FITTED — only one ear wired on GPIO{HW_PWM_GPIO}"
                )
            reached = self.ear.move_to(target)
            other = "R" if WIRED_EAR == "L" else "L"
            return (
                f"WARN EAR {WIRED_EAR} → {self._fmt(reached)}° (AD002, GPIO{HW_PWM_GPIO} hw PWM) · "
                f"EAR {other} NOT_FITTED — only one ear wired on GPIO{HW_PWM_GPIO}"
            )
        if side != WIRED_EAR:
            return (
                f"ERR EAR {side} NOT_FITTED — the servo wired on GPIO{HW_PWM_GPIO} "
                f"is ear {WIRED_EAR}; wire ear {side} (or change WIRED_EAR) to drive it"
            )
        if self.dry_run:
            return f"EAR {side} → {self._fmt(target)}° (dry run, no hardware)"
        reached = self.ear.move_to(target)
        return f"EAR {side} → {self._fmt(reached)}° (AD002, GPIO{HW_PWM_GPIO} hw PWM)"

    # -- main dispatch --------------------------------------------------------
    def handle(self, raw_input: str) -> str:
        raw = raw_input.strip()
        tokens = raw.upper().replace("?", "").replace(".", "").replace(",", "").split()
        if not tokens:
            return "ERR empty command"
        head, *rest = tokens
        joined = " ".join(tokens)

        if head in ("HELP", "?"):
            return (
                "COMMANDS (real on this Pi): EAR L|R|BOTH UP|FLAT|DROOP|<deg> · STATUS · POS · HELP · "
                "NOT_FITTED yet: PAN · TILT · DRIVE · FACE · LED · DISPLAY · TEMP · VOLT"
            )
        if head in ("STATUS", "STAT"):
            return (
                f"BOBBY PI · EAR-{WIRED_EAR} {self._fmt(self.ear.deg)}° (GPIO{HW_PWM_GPIO} hw PWM) · "
                f"EAR-{'R' if WIRED_EAR == 'L' else 'L'} NOT_FITTED · "
                f"PAN/TILT/DRIVE/FACE/LED/DISPLAY/TEMP/VOLT NOT_FITTED — Pi bench, ear proof only"
            )
        if head == "POS":
            return (
                f"EAR-{WIRED_EAR} {self._fmt(self.ear.deg)}° · "
                f"EAR-{'R' if WIRED_EAR == 'L' else 'L'} NOT_FITTED · PAN/TILT NOT_FITTED"
            )

        # Ears: EAR L FLAT · LH EAR FLAT · EAR R 45 · EAR BOTH UP
        ear_side = None
        ear_args: list = []
        if head in ("EAR", "EARS"):
            side_tok = rest[0] if rest else ""
            if side_tok in ("L", "LH", "LEFT"):
                ear_side = "L"
            elif side_tok in ("R", "RH", "RIGHT"):
                ear_side = "R"
            elif side_tok == "BOTH":
                ear_side = "BOTH"
            ear_args = rest[1:]
        elif head in ("LH", "RH"):
            ear_side = "L" if head == "LH" else "R"
            ear_args = [t for t in rest if t not in ("EAR", "EARS")]
        if ear_side:
            return self._do_ear(ear_side, ear_args[0] if ear_args else "")

        # Everything else: honest NOT_FITTED, same vocabulary as the bench.
        if head == "PAN":
            return "ERR PAN NOT_FITTED — no pan servo wired on the Pi bench yet (ZOSKAY on D6 comes with the Ventuno)"
        if head == "TILT":
            return "ERR TILT NOT_FITTED — no tilt servo wired on the Pi bench yet (D9 comes with the Ventuno)"
        if head in ("DRIVE", "FWD", "BACK", "STOP"):
            return "ERR DRIVE NOT_FITTED — no motors wired on the Pi bench"
        if head == "FACE":
            return "ERR FACE NOT_FITTED — no display attached to the Pi bench"
        if head in ("LED", "LEDS"):
            return "ERR LED NOT_FITTED — no lobe LEDs wired on the Pi bench yet"
        if head in ("DISPLAY", "SCREEN"):
            return "ERR DISPLAY NOT_FITTED — no display attached to the Pi bench"
        if head == "TEMP":
            return "ERR TEMP NOT_FITTED — no temp sensor on the Pi bench (MCP9808 comes with the head)"
        if head in ("VOLT", "VOLTS"):
            return "ERR VOLT NOT_FITTED — no bus voltmeter on the Pi bench"
        return f'ERR unknown command "{joined}" — try HELP'


def self_test() -> int:
    """Parse every bench command with no hardware; print command -> reply."""
    bridge = Bridge(dry_run=True)
    cases = [
        "HELP",
        "STATUS",
        "POS",
        "EAR L FLAT",
        "LH EAR FLAT",
        "EAR R 45",
        "EAR BOTH UP",
        "EAR L DROOP",
        "EAR L 200",
        "EAR L",
        "PAN FULL L",
        "PAN -105",
        "TILT UP",
        "DRIVE FWD",
        "FACE WORRIED",
        "LED 50",
        "DISPLAY ON",
        "TEMP",
        "VOLT",
        "BOGUS",
        "",
    ]
    failures = 0
    for cmd in cases:
        reply = bridge.handle(cmd)
        print(f"> {cmd!r}\n  {reply}")
        if not reply.startswith(("OK", "ERR", "WARN", "BOBBY", "COMMANDS", "EAR")):
            failures += 1
    print(f"\nself-test: {len(cases)} commands, {failures} unexpected replies")
    return 1 if failures else 0


def serve(host: str, port: int) -> None:
    bridge = Bridge(dry_run=False)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((host, port))
        srv.listen(1)
        print(f"Bobby Pi bridge listening on {host}:{port} — Tailscale only, one command per line.", flush=True)
        print("Fitted: one AD002 ear servo on GPIO18 hw PWM. Everything else answers NOT_FITTED.", flush=True)
        try:
            while True:
                conn, addr = srv.accept()
                print(f"Connection from {addr[0]}", flush=True)
                with conn:
                    buf = b""
                    while True:
                        chunk = conn.recv(1024)
                        if not chunk:
                            break
                        buf += chunk
                        while b"\n" in buf:
                            line, buf = buf.split(b"\n", 1)
                            cmd = line.decode("utf-8", "replace").strip()
                            if not cmd:
                                continue
                            print(f"> {cmd}", flush=True)
                            try:
                                reply = bridge.handle(cmd)
                            except Exception as e:  # noqa: BLE001 - never drop the link on one bad command
                                reply = f"ERR bridge error: {e}"
                            print(f"  {reply}", flush=True)
                            conn.sendall((reply + "\n").encode("utf-8"))
        finally:
            bridge.ear.stop()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Bobby Pi bridge — Test Bench to Pi over Tailscale (draft v1).")
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--self-test", action="store_true", help="Parse all bench commands with no hardware and exit.")
    args = p.parse_args(argv)
    if args.self_test:
        return self_test()
    serve(args.host, args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
