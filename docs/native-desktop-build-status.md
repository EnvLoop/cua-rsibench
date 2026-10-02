# Native Desktop build status

Updated 2026-10-02. This note separates executable source from native qualification and model results.

## Current V46 controller source

The current entrypoint is `native_desktop_factory.native_guarded_observation_runtime_v46`, source-manifest binding `1d71eed934f52038984cffdb6df80336aa0f6eea1a5fc94a55a0746742985ee9`. Observation policy hash is `a7da63257bd8f1e8be34a16d032f992b4542d39ecff02499421bad9703b4cf21`. All seven roles use one existing observation capture, retaining its before/after native-state equality and the original current predispatch pair. The earlier last-four-sample claim is explicitly removed. The action guard, current ownership, read-only and focus checks, nonces, Enter resampling and 90/720/1200 budgets remain unchanged.

Nine new observation tests plus five original semantic-guard tests passed. The actual controller image reopened all 1,644 source hashes and checked current bindings without network, provider keys or Tinker. These are source/controller checks; full native activation remains gated.

A fresh real Calc control applied five GUI actions: navigation, cell selection, formula input, commit click and save click. The formula was visible in the retained screenshot, but saved readback remained byte-identical to the original seed and the independent verifier failed. The next probe reported `native_application_account_not_owned`. The underlying active-window cause and the save button's administrative label were not retained and are not proved. No guessed coordinate, format-confirmation explanation, warning-preference change, successful positive or distinct reset is claimed. The owned guest was killed and verified stopped.

Retained failure SHA-256: `533427598400dcc2c9f69023b389fbdec0875365ffbe6be1ae5506692ff683f8`. Immediate saved-readback receipt SHA-256: `b2c34f98bdcb891c627686ce3699b15579f9ca39931984b5647075239ccf42bf`. Owned-cleanup receipt SHA-256: `e841b8acb664e8f508e25fca86b6f67763d438529df882dcc07ebf0bcfafa71b`. Model calls, Tinker calls and official model outcomes are zero.

The next qualification diagnostic must retain the current native button label and post-save screenshot plus active-window process, class and transient-parent evidence before cleanup. It must not turn the unproved window transition into qualification credit.

## Preserved earlier epochs

The tested V44 entrypoint is `native_desktop_factory.native_editor_runtime_v44`. Its `source` and `public-binding` commands perform no provider calls. The frozen source-manifest binding is `59df1f4b94f707310d7e903734ef0d94904bbcd28e7fd8249b9c3fa5966c06f2`. The same guest class serves all seven actor paths and Calc, Writer, and Impress. Native qualification remains required before model dispatch.

V44 preserves raw native flags, the original physical leaf checks, ownership and lease checks, and the 720-second actor budget. It adds two explicit contracts for the observed LibreOffice 7.3.7 GTK build: positive current Edit Mode plus application read-only evidence for the omitted SENSITIVE flag, and native Table index/position equality for non-active virtual-cell instances. The evaluator-only local UNO query exposes no generic Office API to actors.

The combined V41–V44 offline checks passed 52 tests. An actual fresh public TRAIN Calc control selected Review, selected B4, and entered the required formula through the shared guard without observation pointer hints. The following Tab action was refused because the in-cell paragraph editor did not satisfy the keyboard predicate. The guest was killed and verified stopped. The formula was not independently verified as saved, and no successful reset or native qualification is claimed from that attempt.

V45 is a frozen additive optimization: it captures the bootstrap's exact native Edit Mode forward path, reopens each slot twice with current native identities and PIDs, and still rereads mode and application read-only state. Its source-manifest binding is `7be98e3ac22d0dbe79e81344afdeaabb2476de617e4800ea5464217b676f52fe`; combined checks passed 61 tests. Its planned reference control uses the ordinary observed Accept and Save buttons. No keyboard predicate or time budget is relaxed.

The one actual V45 control applied the Review and B4 clicks. The operator stopped it at approximately 559 actor seconds while it was still collecting native observations, before formula typing or Save. Its process ended, the owned guest kill was acknowledged, and running-after-kill was false. No saved positive or distinct reset was completed. Full native probes still took roughly 20–33 seconds in the retained readiness sequence, so this optimization did not establish usable performance qualification.

The seven-sample readiness loop is part of the shared frozen actor transport (`semantic_native_transport_v23.py`, lines 25 and 100–104), not an extra private reference loop. Each sample performs native probes before and after the screenshot. The normal reference driver and model/teacher guests share this path. The native guard separately validates observation and predispatch evidence; reducing readiness would require an explicit uniform transport amendment and fresh controls.

Model calls and Tinker calls in these controls are zero. Cloud runtime cost is unknown (`null`). Historical failed controls are retained under their original source epochs and receive no promotion. Native qualification, Enter-component coverage, and student/teacher outcomes remain separate pending gates.

The earlier [V42 proposal](native-desktop-v42-compatibility-proposal.md) is historical and is not the current build-status authority.
