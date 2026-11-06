# Conservative static-button templates

Enabled whole-label templates: **F/C, Check, Fold and Raise**. Bare Call, Bet, variable amounts and all unknown labels retain the existing OCR path. Six masks from four real source images are recorded with source hashes, rectangles and template hashes in `table_reading/button_template_assets/provenance.json`. No font-rendered templates were invented.

## Coverage expansion

The original small Fold/Raise prototypes abstained on larger real labels. Rather than lower thresholds, two larger masks were extracted from `_72432B1C…aff0428c.png`, visibly showing Fold / Call 2.0 BB / Raise. Neither `_ABCB3886…aaed78f0.png` nor `_C998F597…475524bf.png` contributed to the atlas; both independently matched Fold (IoU 0.9962) and Raise (0.9827). `_8C143E80…2a4e7ea0.png` independently matched Fold and provided a visually checked **Bet** example; Bet remains OCR because only one such source is identified. No bare Call example was found in the inspected rows.

The new real labels and source hashes are saved in `button-additional-labels.json`. Candidate rectangles locate the real image regions; this exercise is button-reader coverage, not new detector accuracy evidence. The existing 22 detected regions were inspected visually as bottom-row contact sheets; no claim is made that all 54 full sources have exhaustive button annotations.

## Recognition and fallback

The whole ink mask includes suffix/amount pixels: matching is never based on a word prefix. Thresholds remain aspect tolerance 3.5%, IoU 0.90, inter-label margin 0.12. Multiple exemplars compete by maximum per label, so two same-label prototypes do not create false ambiguity. Invalid/missing assets or mismatched SHA-256 disable the entire atlas, including competitor templates. Input size/aspect are bounded before resize.

Ambiguity and unsupported labels use the original OCR. Injected `_ocr` always bypasses templates. Template evidence is `WHOLE_LABEL_TEMPLATE`, with no invented `ocr_readings`. F/C still makes the entire row preselection; actions and hero-turn confirmation remain disabled.

## Validation

- **16/16 real crops** preserve semantic output with templates enabled versus disabled.
- **17 template hits**, including **10 hits in 11 crops whose source PNGs never contributed to template construction**. Four newly annotated rows additionally match their visually transcribed labels.
- Variable Call 1.0/1.6/2.0/13.5 and Pagar remain OCR; amounts are preserved. Bet also remains OCR. Empty/unsupported rows remain unchanged.
- OCR subprocess calls across this replay: **66 → 32**. This count is not a latency benchmark.
- **17 unit tests** pass, including whole suffix handling, ambiguity, atlas hash/missing-member failure, extreme aspect, injected OCR bypass and evidence/preselection semantics.
- Shared expanded-rank atlas replay: **18 exact, zero accepted wrong, five abstentions** across 23 board transformations (`board-expanded-atlas-regression.json`). This is separate from button coverage.

These are reused development images. Source-disjoint verification excludes the entire PNG used in atlas construction, but it is not a production accuracy estimate or a live Windows test.

```sh
python tools/build_button_templates.py --assets "$VISUALPILOT_ASSETS"
python -m unittest test_button_templates test_action_buttons -q
python tools/validate_button_templates.py --assets "$VISUALPILOT_ASSETS" --output docs/table-reading/button-expanded-validation.json
```

The builder verifies original source hashes and the rebuilt mask hashes. The earlier `button-template-validation.json` preserves the initial smaller coverage result; current expanded evidence is `button-expanded-validation.json`.
