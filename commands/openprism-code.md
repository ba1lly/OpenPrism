---
description: Multi-model coding panel — best-of-N candidates, judge selects + repairs
argument-hint: "<coding task>"
---

Call the `mcp__openprism__code` tool with `task` set to:

$ARGUMENTS

Then present the tool's final solution and its "Verify by:" line. The judge has
already selected and repaired the strongest candidate — relay it rather than
re-solving. If a "Verify by:" command is given and we're in a suitable project,
offer to run it.
