---
type: result-report
title: A0-R2 SmolLM2 bounded feasibility
description: Instrumentation-only compatibility result and guard limitation.
status: verified
last_verified: 2026-08-15
---

# A0-R2 bounded feasibility result

The one authorized CPU float32 feasibility probe completed on
`HuggingFaceTB/SmolLM2-360M` at revision
`f8027fd0eaeea54caa13c31d31b9fdc459c38b49`. It used one fixed synthetic
25-token prompt, two non-generative forward passes, local-only files, and no
sealed targets. No model output content was retained.

The schema-valid receipt reports `compatible`: fast-tokenizer offsets were
available; the hidden-state tuple contained the expected 33 entries; tuple
index 32 was available; the final hidden shape was `[1, 25, 960]`; logits had
shape `[1, 25, 49152]`; all checked values were finite; and the maximum absolute
logit difference between the two passes was `0.0`.

Measured process peak RSS was 2,540,519,424 bytes, below the frozen 8 GiB
reporting ceiling. Total measured runtime was 3.813451875 seconds, including
0.231746083 seconds for model load and forward passes of 0.154995458 and
0.060374250 seconds.

## Guard limitation

After the receipt was written, the outer CCP guard exited with code 70 because
cleanup was uncertain at the `completed descendant seal` stage. A subsequent
read-only observation found admission inactive, an empty queue, no matching
model or guard process, and resource decision `admit`. That observation does
not retroactively upgrade the guarded execution to PASS. The run was not
repeated.

This result is instrumentation-only and evidence-ineligible. It establishes
runtime compatibility under the bounded probe; it is not evidence for latent
TRIZ, does not authorize sealed R2 execution, and does not promote any claim.
