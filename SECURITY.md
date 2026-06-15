# Security

## Reporting

Found a vulnerability? Please open a private security advisory on the GitHub repo
(Security → Report a vulnerability) rather than a public issue. We'll respond as
soon as we can.

## Threat model & what OpenPrism does with your data

- **Provider keys are never logged.** The `direct` backend passes keys only to the
  OpenAI-compatible client. The `opencode` backend never sees keys at all —
  opencode holds the credentials and OpenPrism only calls its local API.
- **The opencode local API can expose provider keys** on its port — its
  `/config/providers` endpoint returns them. OpenPrism deliberately queries only the
  **keyless `/provider`** endpoint (model list + connection status) and never reads
  `/config/providers`, so it never receives credentials. Still, bind the opencode
  server to localhost and set `OPENCODE_SERVER_PASSWORD` if you expose it, since
  anything else on that port could read the keys.
- **Panelists can browse the web** (research mode, opencode backend: `webfetch` /
  `websearch`). They run with **mutation tools denied** (`bash`/`edit`/`write` are
  off) by default. Setting `OPENPRISM_PANEL_TOOLS=all` re-enables `bash`/`edit`/
  `write` for panelists — only do this if you understand that multiple model agents
  will then be able to run commands and modify files on your machine.
- **Prompts and panel answers** are sent to whichever providers/models you select
  (directly, or via opencode). OpenPrism adds no telemetry and phones home to
  nothing — everything runs locally.

## Other notes

- **Autospawned opencode inherits OpenPrism's environment.** When OpenPrism starts
  its own `opencode serve`, that child inherits the parent env (which may include
  provider keys loaded from `.env`). This is intentional — opencode needs its own
  provider env — but it means those vars are in scope for the spawned server.
- **Remote opencode URLs.** `OPENPRISM_OPENCODE_URL` is used as-is (scheme is
  validated to be http/https). Point it only at a server you trust — prompts and,
  if you set `OPENCODE_SERVER_PASSWORD`, that credential are sent to it.

## Secrets hygiene

Keep `.env` and `providers.json` out of version control (both are in
`.gitignore`). Use `openprism doctor` to confirm your setup without printing keys.
