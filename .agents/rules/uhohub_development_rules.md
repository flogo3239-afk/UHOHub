---
name: uhohub-development-rules
description: Essential release safety, PyInstaller updater invariants, and localization guidelines for UHO Hub.
trigger: always_on
---

# UHO Hub Development & Release Guidelines

1. **Release Policy (Local-First Testing & Strict GitHub Gate)**:
   - **STRIKTE REGEL:** Alle Codeänderungen, Bugfixes und neuen Features werden **AUSSCHLIESSLICH LOKAL** kompiliert und nach `C:\Users\louis\Desktop\UHOHub.exe` und `UHOHub.zip` kopiert.
   - **KEIN AUTOMATISCHER GITHUB-UPLOAD:** Führe niemals `git push` aus und erstelle niemals ein GitHub-Release/Tag während normaler Bugfixes oder Weiterentwicklungen.
   - **STRIKTES FRAGE-VERBOT:** Frage den Nutzer **NIEMALS**, ob auf GitHub hochgeladen oder ein Release erstellt werden soll. Schlage niemals proaktiv einen GitHub-Upload vor.
   - **NUR BEI EXPLIZITEM BEFEHL:** Ein Upload oder Release auf GitHub darf **ausschließlich dann** erfolgen, wenn der Nutzer im aktuellen Prompt von sich aus direkt und unmissverständlich den Befehl gibt (z. B. *"Lade das jetzt auf GitHub hoch"* oder *"Release auf GitHub"*).
   - Vor jedem tatsächlichen Release-Upload muss `CURRENT_APP_VERSION` in `app.py` zuerst hochgezählt werden.

2. **PyInstaller Updater & Binary Safety**:
   - Always ensure `CURRENT_APP_VERSION` in `app.py` matches the planned release tag before compiling.
   - Always include `multiprocessing.freeze_support()` at the start of `if __name__ == '__main__':`.
   - Ensure the updater batch runner terminates both legacy executable names (`UHOHub.exe` and `OsuTrainingTracker.exe`), runs detached, and launches the new executable via `powershell Start-Process` as a top-level independent process to avoid PyInstaller parent process security validation failures.

3. **Localization & AI Coach Prompts**:
   - All UI elements, error messages, coach responses, and Gemini prompts must remain strictly in German (preserving standard osu! gaming terminology such as Aim, Stream, Burst, FC, and Mods like DT/HR/HD/EZ).

4. **Theoretische Fragen ("Theoretisch" / "Nur Theorie"):**
   - **STRIKTE REGEL:** Wenn der Nutzer in seinem Prompt das Wort **"Theoretisch"**, **"theoretisch"** oder Ausdrücke wie **"nur theoretisch"**, **"reine Theorie"** bzw. **"nichts machen"** verwendet, darf der Agent **KEINERLEI Code-, Datei- oder Systemänderungen** vornehmen.
   - Es dürfen **keine Tools zum Bearbeiten oder Ausführen** (`replace_file_content`, `write_to_file`, `run_command` etc.) genutzt werden, um das Projekt zu modifizieren.
   - Der Agent soll in diesem Fall **ausschließlich die Frage präzise, verständlich und theoretisch beantworten**, die Machbarkeit erklären und das Konzept aufzeigen, ohne etwas umzusetzen.
