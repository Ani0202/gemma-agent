# Paper Track rules (gemma-4-developer-agent-paper), read 2026-11-04 via Kaggle CLI; updated 2026-11-05 from dec 013

Sources: competition pages (Description, Timeline, Evaluation, Submission Requirements, rules,
foundational-rules) and forum topics 754899, 755867, 753871, 749803, 752667, 755176.

## Format and method
- Submit a **Kaggle Writeup** (web "New Writeup" -> Save -> **Submit** button; unsubmitted drafts are NOT judged).
- Required sections: title and subtitle, abstract, introduction, description of research (methods and
  experiments), related works and citations.
- Alternative: instead of writing in the Writeup, attach an arXiv-ready (LaTeX/Word) PDF via the
  "Public Project Link" field (must be public, no login/paywall).
- Optional: public Kaggle notebook (code) in Project Links. Private Kaggle resources/notebooks attached
  become public after the deadline. Code is not required.
- **Limit: 3,000 words max.** RESOLVED (host, threads 743255 and 749546, 2026-10-27; via dec 013): *counted* = title, abstract,
  captions, tables, all other judged text; *not counted* = figures and references. The appendix is supplementary and "not
  guaranteed" to be read. If a PDF is attached, the PDF alone is judged (same limit) and the Writeup text is not. No official counter.
  **Our budget (dec 013): title + abstract + body + captions + tables <= 2,800.** Nothing the rubric needs goes in an appendix;
  provenance, analysis method and how to reproduce stay in the main text.
- Non-archival: does not block other venues. Must be original, **unpublished** research. A prior public
  GitHub repo does NOT count as prior publication (organizer Elan Markowitz, topic 755867).
- Up to 5 submissions/day, 2 final submissions selected; max team size 5. One Kaggle account only.
  Writeups: at most 2 per team (host, 743255); participants report the form allows only one submitted at a time (753195, no host
  answer). **Plan: exactly one Writeup**, written in the Writeup itself (not a PDF) unless there's a reason to switch (dec 013).
  Auto-selection if no final is chosen (754899): no host answer; the rules text says Kaggle auto-selects. With one Writeup this is moot.

## Deadline
- **2026-11-12 23:59 UTC** (Timeline page). The "Deadline Extension" topic (755176) has no body; likely main track.
- Tie-break: paper "entered first". Host (750338): "it would likely be by original submission time"; ties are expected to be
  extremely rare because there are multiple judges. Not definitive. Still submit a complete version early.
- Extension requested (755176), no answer. Nov 12 23:59 UTC stands.

## Judging (5 criteria, each 0-5, averaged; top 3 papers win; rubric scores not shared)
Novelty (new insights, deepens understanding of existing methods); Quality (generality beyond the
competition, transfer to similar problems); Relevance (impact on SWE / agentic learning);
Verifiability (enough detail to understand method, data collection, analysis); Clarity.
Prizes ($35k): Overall Best Paper $15k, Best New Resource $10k, Best New Application $10k.
Suggested topics: PEFT/RL for SWE agents, code-graph comprehension, new tasks/benchmarks, graph reasoning.
Winning papers highlighted at a Google event (e.g. NeurIPS expo workshop).

## Eligibility and team
- To be eligible you must **join the paper competition** and submit a Writeup. **Main-track entry is NOT required.**
- Employees of Google/Kaggle may enter but cannot win.

## Licence and publication terms
- Winners: submission and source code licensed under an OSI-approved licence that does not limit
  commercial use (page says Apache 2.0). Third-party data/models with incompatible licences exempt.
  Winners must also deliver code and documentation, and sign prize and tax forms.
- Warranty: submission is your own original work, no third-party IP infringement (foundational rules 3.14).
- Code sharing: a public GitHub repo is fine (host, 751804). An earlier GitHub repo is not prior publication (host, 755867).
  Private Kaggle notebooks or resources attached to the Writeup become public after the deadline. Judges "will likely look at
  any code" but may not run it, so give a fast run path (750338). No private sharing outside the team.
- Competition Data may be used for academic research, but must not be redistributed (Data Security).
  Organizer says derived labels may be published (749803); text translations should be keyed by instance_id
  with verbatim spans restored by script from the competition data. Our rule: aggregates and repo names only.

## AI-assisted writing policy
- **None found** in any page or forum topic. No disclosure requirement is stated, and AI-written text is not
  prohibited. The warranty of "own original work" is the only related clause. Plan: include a short
  AI-assistance disclosure in the paper anyway (conservative), and have Aniket confirm he is comfortable
  signing the warranty.

## Open questions
Resolved 2026-11-05 (dec 013): word-count scope, tie-break timestamp (likely the original submission), code sharing, prior publication.
Still unanswered: auto-selection with no final chosen (754899; moot with one Writeup); one-vs-two Writeups submitted at once (753195).
