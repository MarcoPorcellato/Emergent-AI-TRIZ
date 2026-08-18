# H1 cognitive pilot packet

This directory contains the target-free, no-model packet for the first real
TRIZ expert pilot. It is ready for collection but is not human evidence yet.

- `protocol.json` freezes the collection boundary and rater coverage.
- `annotation-guide-v1.2.json` is the proposed guide amendment; it must be
  reviewed before collection.
- `cases.jsonl` contains six unlabeled cases. It deliberately contains no
  answer key, model output, source-exposed context, or sealed target.
- `allocation.json` fixes the randomized display order without identifying
  raters.

Each expert must work independently using the blinded workbench and return a
raw file bound to the exact case, guide, allocation, and session hashes. Raw
files are additive artifacts and must never overwrite the synthetic smoke
files under `data/pilot/`.

Collection status is `ready_for_collection`, not `closed` or `validated`.
