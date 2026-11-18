#!/usr/bin/env python3
"""Bobby ear-servo full-range sweep — Wed 2026-11-18.

Sweeps the servo through its full range of motion, back and forth,
4 times, then lets go (slack). For checking the reprinted inner lobe's
fitment — watch for smooth motion, hesitation, or buzz anywhere in
the travel.

Servo under test: Adeept AD002, metal-geared 9g, 180 deg, 4.8-6 V ONLY.

WIRING — same as the Nov 18 test:
  Servo signal (orange/yellow) -> Pi GPIO17
  Servo red  -> 5 V phone charger (+) — USB-A 5 V / 2 A is plenty
  Servo brown/black -> charger (-) AND a Pi GND pin (common ground is the key)
  DO NOT power the servo from the Pi's 5 V pin.
  DO NOT power it from the UBEC rail — 7.4 V exceeds the AD002's 6 V max.

RUN:
  python3 ear-servo-sweep-2026-11-18.py
  Needs gpiozero on the Pi (usually preinstalled).
  For SMOOTH motion (no jitter), also install lgpio:
    sudo apt install -y python3-lgpio
  The script uses lgpio PWM when available, and falls back to gpiozero's
  software PWM (jittery) if it isn't. NOTE: pigpio is NOT an option here —
  it's gone from the Bookworm repos and doesn't support the Pi 5's RP1
  GPIO chip anyway. The first test script masked the jitter with slow
  0.25 s dwells; this faster sweep shows it.
"""

from time import sleep

from gpiozero import Servo
from gpiozero.pins.lgpio import LGPIOFactory

PIN = 17       # signal on GPIO17
CYCLES = 4     # full back-and-forth sweeps
STEP = 0.05    # fine steps so the motion looks smooth
DWELL = 0.08   # seconds per step


def make_servo() -> Servo:
    """lgpio PWM when available (much smoother), else software PWM."""
    try:
        factory = LGPIOFactory()
        print("Using lgpio PWM.", flush=True)
        return Servo(PIN, pin_factory=factory)
    except Exception:
        print("lgpio not available — using software PWM (may jitter).", flush=True)
        print("  Run: sudo apt install -y python3-lgpio", flush=True)
        return Servo(PIN)


def sweep_to(s: Servo, target: float) -> None:
    """Move smoothly from the current position to target (-1..1)."""
    start = s.value if s.value is not None else 0.0
    direction = 1 if target > start else -1
    v = start
    while (direction > 0 and v < target) or (direction < 0 and v > target):
        v = round(v + direction * STEP, 2)
        v = max(-1.0, min(1.0, v))
        s.value = v
        sleep(DWELL)
    s.value = target


def main() -> None:
    s = make_servo()
    try:
        print("Full-range sweep, 4 cycles — watch for hesitation / buzz:")
        s.value = -1.0
        sleep(0.5)
        for cycle in range(1, CYCLES + 1):
            print(f"  Cycle {cycle}: sweeping to max...", flush=True)
            sweep_to(s, 1.0)
            print(f"  Cycle {cycle}: sweeping back to min...", flush=True)
            sweep_to(s, -1.0)
        s.mid()
        sleep(0.5)
    finally:
        s.detach()  # stop sending pulses; servo goes slack
        s.close()
    print("Done. 4 sweeps complete. Servo detached (slack).")


if __name__ == "__main__":
    main()
