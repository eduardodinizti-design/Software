# Observer stabilization — first implementation

Branch fix/observer-integration, based on d3c6e64. Work in progress, NOT a Windows release.

Changes: removed manufactured detections for missing NumPy/list inputs; HSV felt-candidate extraction replaces black-background projection; exact contour dimensions; conservative normalized-appearance association replaces left-to-right IDs; identical appearances are AMBIGUOUS; per-track integer geometry version. Observer runner now passes the actual Unity frame to the visual tracker and publishes candidate crops through telemetry, with desktop offsets.

All candidates remain unvalidated. Observer bypasses old full-surface single-table OCR and action logic. No production OCR accuracy or complete-table enclosure claim. This is a bounded diagnostic foundation, not finished tracking. Appearance changes may suspend identity; a visual table-ID reader and lifecycle policy remain necessary. Felt bounds may omit cards/buttons. Do not enable gameplay from these candidates.

Validation: Linux, real NumPy/OpenCV synthetic images. Original 12 tracker tests pass; 4 new regressions verify gray background, exact dimensions, identity swap, geometry increment, identical-appearance ambiguity, invalid inputs and out-of-bounds crops. Original OCR-routing test is only a local mock and not proof of real OCR integration.

Pending: capture bounds for this user's Unity surface; validated full-table detector with real images; windows process/API checks; moved/resized real screens; visibility; OCR version fencing; lifecycle recovery; packaged Windows validation. No installer rebuilt or approved.
