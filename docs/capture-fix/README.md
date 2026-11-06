# Strict client capture fix

Base reviewed: 053a1e3278c42712e625b35bed825196bc402d06.

Reproduced before fix: Linux returned a fictitious window and black frame as SUCCESS; failed process queries defaulted to pppoker.exe; arbitrary processes were accepted. Three regressions failed on original code.

One capture engine now serves window_stream.py (standalone), vision_pipeline.py (observer), and the legacy Visualpilot/run_bot.bat entry. Root and app/applet copies are synchronized. Explicit native Windows backend uses typed ctypes GDI calls with GetDC, no pywin32 simulation, and scoped per-monitor DPI. Actual executable must be PPPoker.exe or PPClient.exe; emulator hosts are intentionally not authorized by title. GetClientRect/ClientToScreen identity/geometry are rechecked. Black frames fail closed. GDI resources acquired are released in finally; the client DC is never DeleteDC'd.

Diagnostic: `python windows_capture_diagnostics.py`. If ambiguous, inspect reported candidate HWNDs and run `python windows_capture_diagnostics.py --hwnd NUMBER`. An invalid explicit HWND never silently selects another. Reports persist on failure without fake images. Install numpy, psutil, opencv-python for Windows capture/PNG diagnostics; requirements updated.

Local validation: 22 tests passed, native Windows test skipped in Linux. Tests cover unauthorized processes, denied lookup, missing OS, client dimensions, negative origin, large Unity-sized geometry, ambiguous and explicit selection, changes of PID/process creation/path/origin/size, DPI rejection, black frames, GDI acquisition/cleanup, diagnostics and both entry points.

Windows workflow runs actual GDI on a controlled Tk window, verifying client color pixels, movement/resize and GDI-object stability over 40 captures. It does not install/run PPPoker and cannot approve Unity compatibility. Production never allows Python processes: the Tk test explicitly patches the allowlist in test scope only.

Remaining: native PPPoker/Unity capture, partial occlusion/stale pixels, real multi-monitor/DPI setup, table segmentation and OCR accuracy. A SUCCESS status means capture contract completed, not that a table or cards were recognized. Large surfaces must be segmented before the existing single-table OCR is used. No gameplay or antivirus-evasion changes. No replacement ZIP/installer is released; previous security incident remains separate.
