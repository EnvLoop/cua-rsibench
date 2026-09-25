# Original native-desktop WDI task factory

This is a proposed **LibreOffice Calc, Impress, and Writer** cell. It uses the real LibreOffice GUI in isolated E2B Desktop Linux sandboxes. It is not OSWorld, Microsoft Office, or a scored result. The task packages and verifiers are authored for this repository. The input observations are a frozen 2019–2024 slice of the World Bank's [World Development Indicators](https://datacatalog.worldbank.org/search/dataset/0037712/world-development-indicators) (WDI), licensed [CC BY 4.0](https://datacatalog.worldbank.org/public-licenses). The snapshot contains 1,050 nonmissing observations: 35 countries, five indicators, and six years. It preserves the World Bank API's observed values; EnvLoop authors the layouts, calculations, fictional analyst requests, and scoring rules. These are analytical work simulations on authentic data, not historical work orders.

The pin is `sources/wdi-2019-2024.json`, SHA-256 `cad6aafbd856ebb78f3f50106ab1b5b38ac369a2da251e2442268e296fde6d9f`, fetched 2026-09-25. The WDI response reported `lastupdated: 2026-07-13`. Attribution in each generated document says the derived comparisons are EnvLoop's, not World Bank conclusions. The [source loader](source.py) checks every country-indicator-year key, rejects null/duplicate observations, and refuses a changed snapshot.

## Candidate design and isolation

A private, randomly chosen country split allocates five countries to training, five to selection, and 25 to final candidates. Four original task workflows are generated per country: two Calc audits, one Impress board deck, and one Writer brief. This yields **20 training, 20 selection, and 100 final candidate packages**; the final candidates comprise 50 Calc, 25 Impress, and 25 Writer tasks. Each final country is one analysis source family with four correlated tasks, so family-level uncertainty must cluster by country. The source database is shared WDI; no exact country/observation is shared across splits. Training tasks require one edit, selection two, and final candidates three. **The four structural workflow templates remain shared across splits.** Their semantic `template_group` labels reflect that overlap; this draft intentionally fails the current study's template-disjoint admission gate. A paper could instead preregister within-template transfer before any result, but that change has not been adopted. The private map controls country assignment and defect variants and must remain withheld until final scoring is frozen.

Every package contains an OOXML input, an actor-visible task, an evaluator-only oracle, and SHA-256 bindings. The actor sees screenshots and uses mouse/keyboard in native LibreOffice. It cannot inspect the filesystem, call an Office API, run a terminal, or read the oracle. Trusted setup may upload the input. Trusted evaluation reads the **actor-saved** file before any postprocessing, parses OOXML independently of LibreOffice, checks all required formulas/text plus calculated cached values where applicable, and checks non-target text/table/cell preservation. A new sandbox with the original input is the cold-reset route. The candidate generator is byte-deterministic for the same frozen WDI source and private split map.

Development evidence covers one **exposed train-only Mexico task per application**. Its original input and saved positive/near-miss outputs are in [`dev-fixtures`](dev-fixtures/); the private E2B screenshots and full receipts are retained outside the public repository. The field-limited [receipt](../docs/evidence/native-wdi-original-desktop-development-2026-09-25.json) records nine distinct actor-control sandboxes plus one separate, neutral native save that normalized the Impress input. The initial unnormalized Impress GUI save materially changed untouched text-box geometry and is excluded from the accepted controls; the normalized Impress trio passes the stronger slide-layout guard. **The 25 final Impress candidates have not been normalized.** These development controls do not qualify any final task. The offline [admission gate](admit.py) currently admits **0/100** final identities. No student model was run on this cell.

## Rebuild candidates privately

Use Python with `openpyxl`, `python-pptx`, and `python-docx` installed. All private paths below should be git-ignored. Never commit the split map, final actor instructions, final inputs/oracles, provider credentials, or saved model attempts before the final-task release decision.

```bash
python native_desktop_factory/factory.py \
  --private-map work/native-desktop/private-map.json --new-private-map
python native_desktop_factory/factory.py \
  --private-map work/native-desktop/private-map.json \
  --output work/native-desktop/candidates
python native_desktop_factory/admit.py \
  --candidate-root work/native-desktop/candidates \
  --attempts-root work/native-desktop/final-gui-attempts \
  --out work/native-desktop/admission-audit.json --require-complete
```

The last command **must fail for this v1 pool** because its structural templates overlap across splits and all 100 final GUI receipts are absent. An absent receipt counts as missing, never as a score. The GUI calibration shell supports final candidates only with `--candidate-calibration`; keep all attempts private. After a valid template policy and the 100-task gate pass, convert its evidence into the study's evaluator-owned cell manifest and freeze the runtime/action/verifier bytes before campaign dispatch. The generator itself does not call a model or provider.

## v2 distinct-template candidate inventory

The [v2 factory](factory_v2.py) is the current provisional design. It retains the exposed one-edit train documents, creates substantively different two-factor selection documents, and creates three-edit final decision cases with separate evidence, policy/validation, and provenance structures. Calc has 2/3/4 sheets, Impress 4/5/7 slides, and Writer final tasks add a second rule table. The semantic template groups are disjoint because the actual documents and workflows differ. The source-country split is unchanged and still private. Rebuild offline with:

```bash
python native_desktop_factory/factory_v2.py \
  --private-map work/native-desktop/private-map.json \
  --output work/native-desktop/candidates-v2
```

The v2 factory regenerated the same 140 candidate package bytes on a second run. Its final candidate pool still requires per-ID native-GUI qualification; the [field-limited v2 receipt](../docs/evidence/native-wdi-v2-final-gui-calibration-2026-09-25.json) reports **4/100 private final GUI controls passed across two source-country families** and **96/100 absent**. Exactly one of 25 final Impress inputs underwent a neutral LibreOffice normalization and subsequent fresh actor calibration. This engineering gate does **not** admit a full-study final identity or produce a model result. The original v1 shared-template pool above remains historical development evidence and must not be used as the frozen final denominator.

## Remaining work before a publishable final cell

- Run the native GUI and independent positive/near-miss/reset gate **for each of the 100 final identities**, including all three required edits. Verify the actor's saved file before any evaluator correction. Preserve screenshots and actual file bytes privately.
- Confirm the v2 split-template design in a pre-campaign freeze; its physical structure differs across train/selection/final, but transfer difficulty and discrimination still need controlled training/selection pilots. Merely renaming template labels would be invalid.
- Confirm that the stock E2B Desktop image is stable across runs, pin its image digest, fonts and LibreOffice profile, and measure per-task time/cost ceilings. The three development controls currently bind LibreOffice 7.3.7.2 and its observed executable hash, not an image digest.
- Apply and hash a neutral LibreOffice normalization step to each final Impress input before actor evaluation, then verify the same per-ID non-target geometry guard. The current final-candidate generator emits raw python-pptx files, so those 25 candidates are **not** eligible for admission as-is.
- Audit task difficulty with real model attempts on training/selection only; expand distinct workflows if a single repeated template or too-easy one-cell correction makes the 100-task set weakly discriminating. Do not use final feedback for redesign.
- Freeze task instruction/oracle hashes and hidden-set access before official evaluation; publish the split digest and preregistration. Release final task details only according to the paper's leakage policy.
- Implement any ODF/PDF-specific tasks and independent parsers if those formats are later added. This v1 cell deliberately evaluates saved **OOXML** artifacts; a PDF export is not inferred from a DOCX/PPTX save.
