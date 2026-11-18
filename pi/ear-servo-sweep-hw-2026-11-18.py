#!/usr/bin/env python3
"""Bobby ear-servo full-range sweep — HARDWARE PWM version, Wed 2026-11-18.

The gpiozero / lgpio software-PWM sweeps were jittery on the Pi 5, and a
flaky DuPont signal wire can jitter it too. This version drives the servo
from the RP1 hardware PWM, which is rock-solid timing — if it still
jitters with this, the wire or the power is the problem, not the Pi.

SERVO: Adeept AD002, 4.8-6 V ONLY. 50 Hz, 1-2 ms pulses.
  value -1 -> 1.0 ms pulse (5% duty)
  value  0 -> 1.5 ms pulse (7.5% duty)
  value +1 -> 2.0 ms pulse (10% duty)

SETUP (once):
  1. Move the servo signal wire from GPIO17 (pin 11) to GPIO18 (pin 12).
     Power (red -> 5 V phone charger) and ground (brown -> charger GND
     AND a Pi GND pin) stay exactly as before.
  2. On the Pi, add this line to /boot/firmware/config.txt (under [all]):
       dtoverlay=pwm-2chan
     then: sudo reboot
  3. Install the library:
       pip install rpi-hardware-pwm --break-system-packages

RUN:
  sudo python3 ear-servo-sweep-hw-2026-11-18.py
  (sudo is needed for /sys/class/pwm access.)
"""

from time import sleep

from rpi_hardware_pwm import HardwarePWM

PWM_CHANNEL = 2  # GPIO18 with dtoverlay=pwm-2chan
HZ = 50          # standard servo frame rate
CYCLES = 4       # full back-and-forth sweeps
STEP = 0.01      # ~0.9 deg per step — small steps are what make it look smooth
DWELL = 0.01     # seconds per step (10 ms)


def duty_for(value: float) -> float:
    """Servo value (-1..1) -> duty-cycle percent at 50 Hz."""
    return 7.5 + value * 2.5


def make_pwm() -> HardwarePWM:
    """Pi 5's RP1 shows up as pwmchip2 on some images, pwmchip0 on others."""
    last_error = None
    for chip in (2, 0):
        try:
            pwm = HardwarePWM(pwm_channel=PWM_CHANNEL, hz=HZ, chip=chip)
            pwm.start(duty_for(-1.0))
            print(f"Hardware PWM live: pwmchip{chip}, channel {PWM_CHANNEL} (GPIO18).", flush=True)
            return pwm
        except Exception as e:  # noqa: BLE001 - report and try the next chip
            last_error = e
            print(f"  pwmchip{chip} didn't work, trying the other...", flush=True)
    raise RuntimeError(
        "No hardware PWM channel found — is dtoverlay=pwm-2chan in "
        "/boot/firmware/config.txt, and did you reboot after adding it?"
    ) from last_error


def sweep_to(pwm: HardwarePWM, target: float) -> None:
    """Move smoothly from the current value to target (-1..1)."""
    start = sweep_to.current
    direction = 1 if target > start else -1
    v = start
    while (direction > 0 and v < target) or (direction < 0 and v > target):
        v = round(v + direction * STEP, 2)
        v = max(-1.0, min(1.0, v))
        pwm.change_duty_cycle(duty_for(v))
        sleep(DWELL)
    pwm.change_duty_cycle(duty_for(target))
    sweep_to.current = target


sweep_to.current = -1.0


def main() -> None:
    pwm = make_pwm()
    try:
        print("Full-range hardware-PWM sweep, 4 cycles — watch for hesitation / buzz:")
        sleep(0.5)
        for cycle in range(1, CYCLES + 1):
            print(f"  Cycle {cycle}: sweeping to max...", flush=True)
            sweep_to(pwm, 1.0)
            print(f"  Cycle {cycle}: sweeping back to min...", flush=True)
            sweep_to(pwm, -1.0)
        pwm.change_duty_cycle(duty_for(0.0))
        sleep(0.5)
    finally:
        pwm.stop()  # stop sending pulses; servo goes slack
    print("Done. 4 sweeps complete. Servo detached (slack).")


if __name__ == "__main__":
    main()
