---
name: uhohub-development-rules
description: Essential release safety, PyInstaller updater invariants, and localization guidelines for UHO Hub.
trigger: always_on
---

# UHO Hub Development & Release Guidelines

1. **Release Policy (Local-First Testing)**:
   - Always compile and deploy binaries locally to `C:\Users\louis\Desktop\UHOHub.exe` and `UHOHub.zip` for user testing.
   - NEVER create GitHub releases or push release tags automatically unless explicitly instructed by the user (e.g. "lade es auf github hoch" / "release").

2. **PyInstaller Updater & Binary Safety**:
   - Always ensure `CURRENT_APP_VERSION` in `app.py` matches the planned release tag before compiling.
   - Always include `multiprocessing.freeze_support()` at the start of `if __name__ == '__main__':`.
   - Ensure the updater batch runner terminates both legacy executable names (`UHOHub.exe` and `OsuTrainingTracker.exe`), runs detached, and launches the new executable via `powershell Start-Process` as a top-level independent process to avoid PyInstaller parent process security validation failures.

3. **Localization & AI Coach Prompts**:
   - All UI elements, error messages, coach responses, and Gemini prompts must remain strictly in German (preserving standard osu! gaming terminology such as Aim, Stream, Burst, FC, and Mods like DT/HR/HD/EZ).
