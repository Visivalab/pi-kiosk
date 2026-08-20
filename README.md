# pi-kiosk-setup

Interactive first-boot wizard for Raspberry Pi OS (Bookworm / Trixie, labwc).

The repo must be **public**. Then, on the Pi:

    curl -fsSL https://raw.githubusercontent.com/Visivalab/pi-kiosk/master/kiosk.sh | sudo bash

That downloads only `kiosk.sh`. The script then fetches the rest of the tree
and gives the wizard access to `/dev/tty` so the rotation prompt still works.

Or copy this folder to a Pi / clone it there, then:

    sudo ./kiosk.sh

It asks one question (screen rotation), then applies the rest and prints
what it did after each step.

If a Wayland desktop session is available, rotation is also applied live and
saved for future graphical logins.

This is not an image builder. Flash stock Raspberry Pi OS Desktop 64-bit
with Imager, boot normally, run the command.

## What v1 does

1. Screen rotation selector:
   - No rotation
   - Rotate clockwise (90°)
   - Rotate counterclockwise (90°)
2. Disable screen blanking / sleep
3. Desktop autologin (no password prompt on boot)

The account password is not deleted. It is still used for SSH and sudo.

## What it will not do

- It refuses to run on a non-Raspberry Pi. Safe to invoke by mistake.
- It refuses to run without sudo.
- It does not install Chromium kiosk, RustDesk, or touch mapping yet.
  Those plug in as extra steps later.

## Layout

- `src/pi_kiosk/app.py` — wizard loop. Add a step here, not by forking the CLI.
- `src/pi_kiosk/steps/` — one module per concern (rotation, nosleep, autologin).
- `src/pi_kiosk/host.py` — system port. Tests use an in-memory fake.
- `src/pi_kiosk/linux.py` — the only code that touches a real machine.

Re-running is safe: tagged blocks in `~/.config/labwc/autostart` are replaced,
not duplicated.

## Tests

    make test

Tests never talk to raspi-config or write labwc files on the machine that
runs them.
