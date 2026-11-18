# Bobby Test Rig

Pi-based test software for the Bobby droid, starting with the ears.
The point of this repo: prove each piece on the bench *before* it goes
into the droid, and keep the parameters (servo speeds, clocking, travel
limits) in one place so they transfer directly into the Ventuno's logic
when the real brain arrives.

## The story so far

### Nov 17, 2026 — the ears bind

Joshua assembled the ear servos (Adeept AD002, metal-geared 9g) into the
printed earmote cans. After installing heat inserts, the flat face on the
inner lobe — the part that mounts the earmote to the servo — came out
un-flat. First suspect: a heat insert not seated all the way, rocking
the joint. The fix for that was re-heating the proud insert and pressing
it flush.

### Nov 18, 2026 — the Pi test settles it

A gpiozero test script (`pi/ear-servo-test-2026-11-18.py`) drove one
servo on GPIO17 from a 5 V phone charger: hold min/mid/max, then a slow
sweep. Result:

- Bare servo, out of the can: sweeps fine.
- Installed in the can: **zero movement**. Complete binding.
- Everything removed from the shaft: servos work as advertised.

Servos exonerated. The plastic fitment was the culprit, not the servo.
Decision: reprint the inner lobe — recess the face where the heat
inserts mount, chamfer the mounting-face edges, loosen the fit in the
can, push the lobes away from the can.

### Nov 18, 2026 — the warp

The reprinted lobes warped badly — the flange curled up like the brim
of a top hat. Worst warp Joshua had seen on PETG. Root cause, his call:
the recess (the void in the middle, added Nov 17 to protect the mating
face from proud inserts) thinned the edge to a wafer, and a wide thin
ring with a hollow middle is a warp machine.

Countermeasures: +1 mm thickness, chamfer on the inner edge, 8 mm
brim, build plate washed and re-glued, fan off for the first layers.
Round-fit check: the lobe's roundness runs through the can with zero
friction — flatness is the last remaining variable. If the new print
comes out flat, the earmotes should sit friction-free.

Outcome, same day: the reprint came out very flat — the fix worked.
Full installed test still to come.

### Nov 18, 2026 — the jitter saga

The sweep script (`pi/ear-servo-sweep-2026-11-18.py`) was very jittery —
on the bare servo *and* the mounted ones. Same jitter on both meant the
signal, not the plastic. The trail:

1. **Software PWM** (gpiozero's fallback, then lgpio) — Linux scheduling
   wobbles the pulse timing. The first slow script masked it with 0.25 s
   dwells; the faster sweep showed it.
2. **pigpio** — dead end. Not in the Bookworm repos, and it doesn't
   support the Pi 5's RP1 GPIO chip anyway.
3. **Hardware PWM** (`pi/ear-servo-sweep-hw-2026-11-18.py`) — the fix.
   Move the signal to GPIO18 (pin 12), add `dtoverlay=pwm-2chan` to
   `/boot/firmware/config.txt`, reboot, `pip install rpi-hardware-pwm`.
   On the Pi 5 the RP1 chip is `pwmchip2` on some images, `pwmchip0` on
   others — the script tries both.
4. **Chunky steps tick.** Even on hardware PWM the sweep ticked at first
   — the script stepped in 4.5° jumps with a pause between each. Fine
   steps (0.01 value / ~0.9° every 10 ms) made it a smooth turn.

Also found along the way: a servo with power but a floating signal wire
twitches on its own — the unconnected pin picks up noise. And DuPont
jumper wires are loose enough to jitter a signal by themselves; the
finished Bobby has zero DuPont in it (JST-XH crimps and ribbon cable)
for exactly that reason.

## Repo layout

```
pi/
  ear-servo-test-2026-11-18.py      # diagnostic: holds + slow stepped sweep (gpiozero, GPIO17)
  ear-servo-sweep-2026-11-18.py     # 4x full-range sweep (lgpio, GPIO17) — jittery, kept for reference
  ear-servo-sweep-hw-2026-11-18.py  # 4x full-range sweep (hardware PWM, GPIO18) — the good one
  earmote_params.py                 # earmote parameters that transfer to the Ventuno
```

## Hardware

- Raspberry Pi 5 (`mechsmithpi5`, user `mechsmith`, 192.168.1.23)
- Adeept AD002 servo: metal-geared 9g, MG90S-class, 2.0 kg·cm @ 4.8 V,
  180°, **4.8–6 V only** (never the 7.4 V UBEC rail)
- 5 V phone charger (USB-A, 2 A) for servo power — never the Pi's 5 V pin

## Wiring (all three scripts)

```
Servo signal (orange/yellow) -> GPIO17 (pin 11) for the gpiozero/lgpio scripts
                             -> GPIO18 (pin 12) for the hardware-PWM script
Servo red  -> 5 V phone charger (+)
Servo brown/black -> charger (-) AND a Pi GND pin (common ground is the key)
```

## Running the hardware-PWM sweep (the good one)

```bash
# once: enable hardware PWM, then reboot
echo "dtoverlay=pwm-2chan" | sudo tee -a /boot/firmware/config.txt
sudo reboot

# once: install the library
sudo pip3 install rpi-hardware-pwm --break-system-packages

# every run (sudo is needed for /sys/class/pwm access)
sudo python3 pi/ear-servo-sweep-hw-2026-11-18.py
```

## Earmote parameters

`pi/earmote_params.py` holds the numbers the Ventuno will need:
servo model, voltage limits, PWM frame rate and pulse widths, sweep
speeds, and clocking (rest/center angles — still to be measured from
the installed geometry). Edit the params, not the scripts, when the
numbers change.
