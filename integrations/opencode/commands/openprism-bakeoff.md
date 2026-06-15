---
description: Blind-judge two models on one prompt to decide which earns a panel seat
---

Below are the arguments. Parse them as: the first whitespace-separated token is
`model_a`, the second token is `model_b`, and everything after the second token is
the `question` prompt.

Call the `openprism_bakeoff` tool with those three values, then show me the verdict
including the final `WINNER:` line.

Arguments: $ARGUMENTS
