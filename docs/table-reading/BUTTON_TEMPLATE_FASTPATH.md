# Conservative static-button templates

Enabled whole-label templates: **F/C and Check**. Fold and Raise remain diagnostic competitors only; Call, Bet, variable amounts and all unknown labels retain the existing OCR path. No system-font templates were invented.

Four prototype masks come from three real source images. Their source hashes, table/button rectangles and template hashes are in `table_reading/button_template_assets/provenance.json`; `tools/build_button_templates.py` reproduces them. Labels were visually checked on the extracted masks.

The recognizer preserves the entire text mask, including amount/suffix ink; it never matches only a word prefix. It requires aspect agreement within 3.5%, whole-mask IoU at least 0.90 and competitor margin at least 0.12. Ambiguity, any absent/invalid atlas member, extreme aspect or invalid input falls back to OCR. Fold/Raise cannot be accepted even when their prototype matches perfectly. Injected `_ocr` always bypasses templates.

Template successes carry `WHOLE_LABEL_TEMPLATE` evidence, not fabricated `ocr_readings`. F/C still changes the entire button row into preselection: neither Check nor any neighboring label becomes a currently available action. `hero_turn_confirmed` and `actions_allowed` remain false.

## Validation

- Twelve real table crops compared with templates enabled/disabled: all semantic outputs unchanged.
- Eight crops use source PNGs absent from template construction. Five template hits across four such sources: four F/C and one Check, all preserving OCR semantics.
- Variable Call 1.0/1.6 labels, Pagar and empty button regions remained on the previous path; no variable amount was discarded.
- Seventeen unit tests pass (ten new, seven existing), including missing-competitor fail-closed behavior, extreme aspect, ambiguity, suffix preservation, injected OCR bypass and preselection/evidence semantics.
- Shared rank-template regression on 23 board transforms remains 18 exact, zero wrong accepted and five abstentions (`board-template-regression.json`). That board result is separate from button-template validation.

The comparison uses development images and preserved OCR output; it is not a complete independent human-labeled button dataset or Windows live validation. Fold/Raise await source-disjoint evidence; Call/Bet await suitable real source exemplars. No performance claim follows from these correctness tests alone.

```sh
python -m unittest test_button_templates test_action_buttons -q
python tools/validate_button_templates.py --assets "$VISUALPILOT_ASSETS" --output docs/table-reading/button-template-validation.json
```
