# bin/kaggle-submit backlog (dec 048 item 3). Do these ONLY inside the next guard change that's needed anyway, never as a standalone round before Nov 6.
- (a) Ordering: in the server-side pre-check, refuse unless the date column is non-increasing (newest-first), so the today-check stays valid under any page cap.
- (b) Repeat submissions: "sha:<prefix> in description" refuses any re-submission of a sha, but slot policy allows repeating the best bundle
  to measure LB variance. Before the first repeat is proposed, design a Director-authorized repeat path (e.g. an AUTHORIZE field repeat=N
  that relaxes the sha-prefix and local single-use rules to "no row today" for that N) and get it reviewed.
- Known limitation (dec 048 item 1, NON-BLOCKING): the pre-check assumes the server honours --page-size 100 (the CLI prints no next-page token).
- (c) Duplicate JSON keys in a ledger line silently use the last value (v6 review NON-BLOCKING 1): reject duplicates via object_pairs_hook in the next guard change.
- (d) Per-track submit-kernel selection inside the guard (dec 054 item 4); today SUBMIT_KERNEL in config.env is set per submission by its own commit.
