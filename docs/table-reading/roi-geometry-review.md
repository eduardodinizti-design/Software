# Current-crop ROI geometry — 2026-11-06

`roi_geometry.get_roi(width,height,region='board',layout='BLUE_COLORED_V1')` centralizes the existing board band: x 17–85%, y 35–50%, using the identical Python rounding. Dimensions are obtained from the freshly detected table array; host-window client dimensions are not substituted. Moving a table does not change its local ROI; resizing requests a distinct geometry entry.

The cache holds at most 128 immutable rectangles keyed by width, height, region and layout. No frame, pixel buffer, card reading or absolute table position is cached. `Rect.translated` can convert local diagnostics to frame coordinates without inserting position into the cache. Unsupported profiles and non-positive/non-integer dimensions raise a clear error. Empty image arrays return `INVALID_CROP` from the board reader.

This is a geometry-validity and bounded-memory change. Four multiply/round operations were already cheap; no performance gain is claimed and no OCR benchmark was added.

Seven new tests cover exact bounds at five sizes, translation including negative origins, resize and 500-key eviction, immutability, invalid input/profile, current-pixel slicing and empty crops. Existing board tests retain reading/state validation separately.
