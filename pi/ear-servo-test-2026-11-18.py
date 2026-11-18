#!/usr/bin/env python3
"""Bobby ear-servo powered test — Wed 2026-11-18 (daytime work break).

Question it answers: is the inner lobe actually binding in the earmote can,
or is the stiffness just the back-drive torque of an unpowered servo felt
by hand? (Unpowered servos always feel stiff — the powered sweep settles it.)

Servo under test: Adeept AD002, metal-geared 9g, 180 deg, 2.0 kg-cm @ 4.8 V,
4.8-6 V ONLY. Confirmed Nov 16 as a perfect fit in the earmote cans.

WIRING — one servo at a time:
  Servo signal (orange/yellow) -> Pi GPIO17
  Servo red  -> 5 V phone charger (+) — USB-A 5 V / 2 A is plenty
  Servo brown/black -> charger (-) AND a Pi GND pin (common ground is the key)
  DO NOT power the servo from the Pi's 5 V pin.
  DO NOT power it from the UBEC rail — 7.4 V exceeds the AD002's 6 V max.
  (The ear-servo power rail on the Aorta board is still unresolved, 5 V vs
  UBEC — this bench test is 5 V regardless.)

RUN:
  python3 ear-servo-test-2026-11-18.py
  Needs gpiozero on the Pi:  pip install gpiozero  (usually preinstalled)

PROCEDURE:
  1. OUT of the can first (baseline): run the script, watch the full sweep.
     A healthy servo sweeps smooth, quiet, no buzz at any point.
  2. INSTALLED in the can: run it again, same script.
     Sweep slow and watch/listen where it hesitates, buzzes, or stalls.
  3. Note the value printed when it hesitates — that is where the friction
     lives (lobe edge on the can rim vs inner lobe binding inside the can).
     - Hesitation near the ends of travel -> lobe edge / rim contact.
     - Hesitation through the whole middle -> inner lobe binding in the can.
     - Smooth installed, stiff only by hand -> no binding; it was just
       back-drive torque. Reprint still goes ahead for the flatness fix.

REPRINT (decided Nov 17, regardless of the test): recess the face where the
heat inserts mount, chamfer the mounting-face edges, loosen the fit in the
can, push the lobes away from the can. If redesign + powered test still fail,
fallback is a small radial bearing coaxial with the servo shaft (608-class
or smaller, e.g. 688) — the pan's 51104 thrust bearing (35 mm OD) is too big
for an ear can.
"""

from time import sleep

from gpiozero import Servo

PIN = 17  # signal on GPIO17, as in the Nov 17 chat plan


def slow_sweep(s: Servo, step: float = 0.1, dwell: float = 0.25) -> None:
    """Sweep -1..1 and back in small steps so a bind shows up as a hesitation."""
    v = -1.0
    while v <= 1.0 + 1e-9:
        s.value = round(v, 2)
        print(f"  value={s.value:+.2f}", flush=True)
        sleep(dwell)
        v += step
    v = 1.0
    while v >= -1.0 - 1e-9:
        s.value = round(v, 2)
        print(f"  value={s.value:+.2f}", flush=True)
        sleep(dwell)
        v -= step


def main() -> None:
    s = Servo(PIN)
    try:
        print("Hold positions: min, mid, max (1 s each)")
        s.min()
        sleep(1)
        s.mid()
        sleep(1)
        s.max()
        sleep(1)
        print("Slow sweep out and back — watch for hesitation / buzz:")
        slow_sweep(s)
        s.mid()
        sleep(0.5)
    finally:
        s.detach()  # stop sending pulses; servo goes slack
        s.close()
    print("Done. Servo detached (slack).")


if __name__ == "__main__":
    main()
