# Nov 8 slot proposal (dec 061 item 5; dec 082 item 3). Sent 2026-11-07T06:3xZ, before the 12:00Z due time, from current evidence.
Inputs: U2 = plan 008 arm 2 (31b-v011) NOT SHIP-ELIGIBLE (dec 080, report 019: 8/33 vs 4/33, MECH1/2 FAIL). U1 = 31b-v002 (ref 58072907)
PENDING at the 06:06:50Z poll (results/lb_31b_v002.polls.csv). Arm 3 (v012) has not landed (est. ~12-13Z+), so it cannot feed this slot.
Matrix: ops/drafts/nov8-slot-inputs.md, column "arm 2 not eligible / incomplete".

PROPOSAL (conditional on U1 at slot time, pre-committed now):
- U1 PENDING at slot time -> e4b-v002 REPEAT, dist/e4b-v002.zip sha256=60c0074684ef4f9aa9cd8744d08fa29a37f3b94fc893541a8b96ceed54944dad (dec 079 default).
- U1 ERROR/timeout -> e4b-v002 REPEAT (CAP-BOUND binds for 31B per dec 061 i; no 31B at cap 3.5).
- U1 SCORED with public score >= 0.10 (2x the e4b 0.05) -> 31b-v002 REPEAT, dist/31b-v002.zip sha256=e56a05e5701fa16a8dbbabb304d98f63a465511cefbb28d65850ea5ce086ec88
  (run-to-run noise measured at a non-floor score is more informative). U1 SCORED < 0.10 -> e4b-v002 REPEAT.
Justification: no finals-compliant (hint-free) bundle is both packed and evaluated with a ship-eligible verdict. Arm 2 failed its
ship rule, arm 3 is still running, and e4b-v003 is not packed. So the slot's best use is checklist item l.63 (does the private LB use multiple runs)
and LB noise. Build risk is zero: identical zips, both already SCORED/accepted by the validator. Caveat: both candidates carry the FastAPI hint
(dec 057), so they are not finals, and the write-up must say so. Pre-reqs: e4b repeat needs the reverse SUBMIT_KERNEL config commit (currently 31b kernel,
cefb420), grep-journaled. 31b repeat needs none. One pending submission at a time: never submit while 58072907 is PENDING.
