---
description: Blind-judge two models on one prompt to decide which earns a panel seat
argument-hint: "<model_a> <model_b> <prompt>"
---

Parse $ARGUMENTS as: the first whitespace-separated token is `model_a`, the
second token is `model_b`, and everything after that is the `question`/prompt.

Call the `mcp__openprism__bakeoff` tool with those three values, then show me the
verdict (including the final `WINNER:` line).
