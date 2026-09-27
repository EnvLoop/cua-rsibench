"""Pre-result fair saved-artifact scorer for the original WDI desktop cell.

Keeps all frozen OOXML structure, cached-result, and non-target preservation
guards from the development verifier. It changes only target acceptance:
algebraically equivalent live Calc formulas and unambiguous Writer/Impress
numeric paraphrases can pass. The evaluator supplies a private counterfactual
salt; no actor or researcher receives it. This is not a model result.
"""

from __future__ import annotations

import hashlib

if __package__:
    from .formula_semantics import semantically_equivalent
    from .target_text_semantics import semantically_correct
    from .verify import (digest, docx_content, pptx_slide_shapes,
                         verify as legacy_verify, xlsx_cells)
else:
    from formula_semantics import semantically_equivalent
    from target_text_semantics import semantically_correct
    from verify import digest, docx_content, pptx_slide_shapes, verify as legacy_verify, xlsx_cells


OFFICIAL_SCHEMA = "cua-native-wdi-saved-verifier-v2"


def verify_official(baseline: bytes, saved: bytes, oracle: dict, *,
                    private_salt: str) -> dict:
    if not isinstance(private_salt, str) or len(private_salt) < 32:
        raise ValueError("Evaluator-private semantic salt is required")
    legacy = legacy_verify(baseline, saved, oracle)
    errors = list(legacy.get("errors", []))
    workflow = oracle["workflow"]
    if workflow.startswith("calc-"):
        before, after = xlsx_cells(baseline), xlsx_cells(saved)
        for address, rule in oracle["targets"].items():
            sheet, cell = address.split("!", 1)
            try:
                proposed = after[sheet][cell]["formula"]
            except KeyError:
                proposed = None
            semantic = proposed is not None and semantically_equivalent(
                proposed, rule["formula"], before, private_salt=private_salt)
            code = "target_formula_wrong:" + address
            if semantic:
                errors = [item for item in errors if item != code]
            elif code not in errors:
                errors.append(code)
    elif workflow.startswith("impress-"):
        original = pptx_slide_shapes(baseline)
        candidate = pptx_slide_shapes(saved)
        slide = oracle["target_slide"] - 1
        if slide < len(original) and slide < len(candidate):
            for i, old in enumerate(original[slide]):
                if old not in oracle["targets"]:
                    continue
                code = f"target_text_wrong:slide{slide+1}:shape{i+1}"
                semantic = i < len(candidate[slide]) and semantically_correct(
                    candidate[slide][i], oracle["targets"][old])
                if semantic:
                    errors = [item for item in errors if item != code]
                elif code not in errors:
                    errors.append(code)
    elif workflow.startswith("writer-"):
        original = docx_content(baseline)["paragraphs"]
        candidate = docx_content(saved)["paragraphs"]
        for i, old in enumerate(original):
            if old not in oracle["targets"]:
                continue
            code = f"target_text_wrong:paragraph{i+1}"
            semantic = i < len(candidate) and semantically_correct(
                candidate[i], oracle["targets"][old])
            if semantic:
                errors = [item for item in errors if item != code]
            elif code not in errors:
                errors.append(code)
    else:
        raise ValueError("Unknown native WDI workflow")
    return {**legacy, "schema": OFFICIAL_SCHEMA, "errors": errors,
            "passed": not errors and digest(baseline) != digest(saved),
            "semantic_salt_sha256": hashlib.sha256(private_salt.encode()).hexdigest(),
            "target_count": len(oracle["targets"])}
