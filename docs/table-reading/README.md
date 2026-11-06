# Automatic table rectangles and experimental Hero reading

## Windows: reuse the capture already obtained

On branch `fix/strict-client-capture`, Fetch/Pull in GitHub Desktop, then from the repository root:

```
python ler_mesas.py
```

The default finds the newest successful JSON+PNG pair in logs/diagnostics. It skips failed HWND reports. No new capture or manual rectangle selection is required. Output: logs/leitura/leitura-<snapshot>/resultado.json, mesas-anotadas.png, and mesa-XX.png native-resolution crops. Green = complete geometry candidate, not guaranteed correct OCR. Amber = partial/uncertain/blocked; not sent to OCR.

Optional explicit input:
```
python ler_mesas.py --image PATH.png --metadata PATH.json
```
Optional fresh capture of a currently valid explicitly chosen HWND:
```
python ler_mesas.py --hwnd NUMBER
```

Requires numpy, opencv-python, pytesseract and native Tesseract with English data. If native Tesseract is unavailable, detected crops are still saved with OCR_UNAVAILABLE and a clear console message. Configure TESSERACT_CMD if installed in a nonstandard location. There are no clicks or changes to Windows security settings.

## Scope and identity

Only calibrated blue layout and two Hero cards. Board, other skins, continuous updates and identity tracking across movement remain outside this change. No full-desktop resizing before detection or cropping. Every complete crop goes independently to the reader.

Limit: six complete tables within one source frame per snapshot. More than six blocks all candidate readings rather than silently discarding extra tables. This is not yet a six-window global scheduler.

source_key records PID, process creation time and HWND. Different processes cannot share result identity. snapshot_table_id is temporary; never treat table index as persistent identity. This is preparation for multiple accounts, not proof that an OS process equals a poker account. Four accounts/16 tables are future scope.

## Evidence

- 11 pipeline tests passed in Linux: native crops forwarded exactly, scaled/moved table, six-table success/seven-table refusal, source/snapshot isolation, partial/blank/mismatched input, missing OCR, duplicate card rejection, latest-capture selection and lossless PNG export/quota.
- Real development labels: 8 annotated table regions across 7 screenshots, 8 detected, 16 correct cards, 0 wrong, 0 unknown. Labels predate this integration; images were already used in development, so this is regression evidence, not an independent accuracy estimate.
- Three of those regions were initially checked separately; they are not additional independent samples.
- Tests of six tables use composited real table pixels and an injected reader to check routing; they do not validate simultaneous six-table real Windows operation or OCR accuracy.
- Original capture contracts/native Windows controlled-Tk tests remain in CI. No PPPoker/Unity live instance is available in CI.

The latest user-provided GDI image was visible in chat but not available as an original full-resolution PNG in the local filesystem. This implementation has not run OCR on that exact image yet. The default Windows command reuses that existing file on the user's machine.

## Known limitations

The imported laboratory reader remains experimental, including unresolved wider stress/synthetic failures such as 4/A confusion. CANDIDATE results are not calibrated probabilities and are never authorized for gameplay. Fixed canonical ROIs inside a detected table describe the supported blue layout, not fixed desktop coordinates. Detector can abstain when controls/corner cues are absent or overlays obscure the table. No guarantee of 100% recognition or 30 FPS is made.

Explicit output export is capped at 100 MiB for logs/leitura; this is not the project's global daily-storage limit. Existing files are not silently deleted. Package provenance is in source-provenance.json. No new installer or ZIP is released; the previous Defender issue remains separate.
