# Nov 8 slot proposal: prepared inputs (dec 061 item 5, dec 078 item 2b). DRAFT, not sent. Due to the Director 2026-11-07T12:00Z.
Fill the two unknowns, pick the matching row, and send a 1-paragraph proposal. Every number comes from the files cited.

## Unknowns to fill at send time
- U1: 31b-v002 LB outcome (dec 055 submit 2026-11-07T00:00Z): SCORED <score> / ERROR <status text> / PENDING at 12:00Z. File: results/lb_31b_v002.json.
- U2: plan 008 arm-2 (v011) progress at 12:00Z: complete + verdict / partial (n rows) / not started. Arm-2 ~11.5 h from ~00:30Z, so
  likely NOT complete by 12:00Z. If the verdict lands later the same day, send a 1-line amendment before 2026-11-07T22:00Z.

## Facts on file (as of 2026-11-06T14:50Z)
- e4b-v002: public 0.05, COMPLETE, T = 5.007 h (results/lb_e4b_v002.json). Carries the FastAPI hint (dec 057), so it cannot be a final.
- e4b-v003 (dec 057 item 3 successor without the hint): NOT PACKED. No bundles/e4b/v003. Pack + review is CPU (~1 cycle); the
  smoke needs Kaggle GPU quota after the reset, competing with arm 2 (ONE session) and arm 3 (plan 009, ~12 h).
  "Packed + reviewed + smoke-run" by 12:00Z is not realistic unless a second concurrent Kaggle GPU session is allowed (unverified).
- 31b-v002: cap 3.5, thinking 4096, carries the FastAPI hint -> cannot be a final (dec 057 item 3); its value is cap/runtime validation.
- 31b-v011 (arm 2): cap 3.5, thinking 0, NO repo-named hint, PROMPT-LEVEL guards; dist/31b-v011.zip 4f5b078a...4938, pack + load
  PASS, not yet evaluated. The only finals-compliant 31B with a pending pass-rate number.
- Arm 1 (v009, the v011 parent): 4/33 resolved, empty 12/33 (results/plan007_arm1_summary.json). Local resolved = docker-path env
  (ENV CONTROL caveat, plan 007 l.152).
- FINALS RULE: no final above the H3 cap bound (31B 1.23, e4b 1.0) unless a same-or-higher cap, same model, has SCORED.

## Decision matrix (pre-written; the proposal follows the matching row)
| U1 \ U2 | arm 2 SHIP-ELIGIBLE | arm 2 not eligible / incomplete |
|---|---|---|
| 31b-v002 SCORED | 31b-v011 (first hint-free 31B on the real scorer, at the validated cap) | e4b-v002 repeat (measures LB run-to-run noise; zero build risk) or 31b-v002 repeat (noise at the higher score). Pick the 31B repeat if 31b-v002 >> 0.05. |
| 31b-v002 ERROR / timeout | none at cap 3.5 (CAP-BOUND binds, dec 061 i). e4b-v002 repeat, or hold the slot | same |
| 31b-v002 PENDING at 12:00Z | e4b-v002 repeat (one pending submission at a time; can't stack 31B) | same |
- The repeat's value: open checklist item l.63 (does the private LB use multiple runs?) and LB noise; both affect how much one LB
  number can say about any later bundle. 0.05 is near the floor (~6/120), so an e4b repeat says little about noise at higher scores.
- Not proposed: e4b-v003 for Nov 8 (not packed and no smoke). Proposal: pack + review e4b-v003 on CPU Nov 7, smoke it when quota
  allows, aim for a Nov 9-10 slot (validated well before Nov 29 per the FINALS RULE).
- DEC 079 item 3 (00:09Z Nov 7): if U1 still PENDING at 12:00Z, DEFAULT = e4b-v002 repeat (matrix row 3). Pre-req at submit time:
  reverse config commit SUBMIT_KERNEL -> e4b kernel (config.env currently = aniket0202/gemma-submit-31b, cefb420), grep-journaled.
