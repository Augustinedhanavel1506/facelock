# FaceLock — J.A.R.V.I.S.-style Face Lock

A local desktop app: a full-screen, Iron Man/J.A.R.V.I.S.-styled HUD that uses your
webcam to recognize your face and unlock, instead of typing a password every time.

**Important — what this actually does:** Windows' real sign-in screen runs on a
protected "Secure Desktop" that outside apps can't inject input into, so this does
**not** replace Windows login. Instead it's your own lock screen: trigger it whenever
you step away, and it locks your view until your face (or a backup PIN) is verified.
Your camera images and model never leave your PC — everything in `data/` is local.

## Running it

Double-click **`Run FaceLock.bat`** — it starts silently in the system tray (bottom-right,
arc-reactor icon). First run launches the enrollment wizard automatically.

Tray icon → right-click for the menu:
- **Lock Now** (or press `Ctrl+Alt+L` anywhere) — show the lock HUD immediately
- **Enroll / Re-scan Face...** — (re)train your face profile
- **Set Backup PIN...** — change the fallback PIN (shown when you press `P` on the lock screen)
- **Start with Windows** — check this to have FaceLock launch automatically at login

## How unlocking works

The HUD scans continuously; once your face is confidently matched for enough
consecutive frames, it shows "ACCESS GRANTED" and dismisses itself. If the camera
can't recognize you (bad lighting, camera off, etc.) press **P** on the lock screen
and enter your backup PIN instead — you can never be locked out by the camera alone.

## Notes / limitations

- This is a convenience layer, not a substitute for real OS security — a printed
  photo can potentially fool the recognizer (LBPH has no liveness check). Don't rely
  on it to protect anything highly sensitive; the PIN fallback is stored as a salted
  hash locally, and enrollment photos live only in `data/samples/` on this machine.
- The default hotkey is `Ctrl+Alt+L` (see `facelock/config.py` → `GLOBAL_HOTKEY`) —
  change it there if it collides with another app you use.
- Only covers your primary monitor.

## Manual setup (if you ever need to reinstall)

```
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python main.py
```
