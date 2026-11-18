"""Earmote parameters for the Bobby droid.

One place for the numbers that start life on the Pi test rig and transfer
directly into the Ventuno's logic. Edit the params, not the scripts, when
a number changes.

Servo: Adeept AD002, metal-geared 9g, MG90S-class.
"""

# --- Servo identity -------------------------------------------------------
SERVO_MODEL = "Adeept AD002"
SERVO_TORQUE_KG_CM = 2.0        # at 4.8 V
SERVO_TRAVEL_DEG = 180
SERVO_VOLTAGE_MIN = 4.8         # never below
SERVO_VOLTAGE_MAX = 6.0         # NEVER the 7.4 V UBEC rail
SERVO_SPEED_S_PER_60DEG = 0.10  # MG90S-class rating at 4.8 V; verify on the bench

# --- PWM signal (Pi test rig) ---------------------------------------------
PWM_HZ = 50                     # standard servo frame rate (20 ms period)
PULSE_MIN_MS = 1.0              # value -1
PULSE_MID_MS = 1.5              # value 0
PULSE_MAX_MS = 2.0              # value +1

# Pi 5 hardware PWM: signal on GPIO18 (pin 12), dtoverlay=pwm-2chan.
# The RP1 chip is pwmchip2 on some images, pwmchip0 on others.
HW_PWM_GPIO = 18
HW_PWM_CHANNEL = 2

# --- Sweep (bench test) ----------------------------------------------------
SWEEP_CYCLES = 4
SWEEP_STEP = 0.01               # servo value per step (~0.9 deg); fine steps = smooth
SWEEP_DWELL_S = 0.01            # seconds per step (10 ms)

# --- Earmote clocking (Ventuno logic) ---------------------------------------
# Angles are servo value (-1..1); 0 is the horn's mid position.
# TODO: measure from the installed geometry once the flat reprint is in.
EAR_REST = 0.0                  # at-rest ear position
EAR_MIN = -1.0                  # full travel one way
EAR_MAX = 1.0                   # full travel the other way


def duty_for(value: float) -> float:
    """Servo value (-1..1) -> duty-cycle percent at PWM_HZ."""
    span_ms = PULSE_MAX_MS - PULSE_MIN_MS
    pulse_ms = PULSE_MID_MS + value * (span_ms / 2.0)
    return pulse_ms / (1000.0 / PWM_HZ) * 100.0
