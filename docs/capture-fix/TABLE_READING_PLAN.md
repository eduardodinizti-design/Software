# Next milestone: automatic table crop and experimental Hero reading

Focus: one real blue PPPoker table inside a large GDI frame. Preserve native pixels for OCR. Max 6 complete proposals per snapshot. Four accounts / 16 tables are future scope, not enabled.

Use calibrated detector and Hero reader from laboratory source, not the unvalidated 0.50-template pipeline. Results keyed by process creation/PID/HWND and snapshot UUID; table indices are not persistent identities or account IDs. No gameplay, clicks, board-reading claims or continuous tracking. Reuse latest saved successful capture to avoid another user capture round.

Validation: real development screenshots for pixel detection and recognition; scaled/moved composites for coordinates and six-table limit; no-table/partial fixtures; source isolation; actual cropped pixels passed to reader. Existing single user GDI PNG is shown in chat but unavailable as a full-resolution local file, so no claim to have run OCR on it.
