# Security

## Reporting

Found a vulnerability? Open a private security advisory on the GitHub repo (the
Security tab, "Report a vulnerability") rather than a public issue. We'll respond as
soon as we can.

## Threat model and what OpenPrism does with your data

- **Provider keys are never logged.** The `direct` backend passes keys only to the
  OpenAI-compatible client. The `opencode` backend never sees keys at all; opencode
  holds the credentials and OpenPrism only calls its local API.
- **The opencode local API can expose provider keys** on its port: its
  `/config/providers` endpoint returns them. OpenPrism deliberately queries only the
  keyless `/provider` endpoint (model list and connection status) and never reads
  `/config/providers`, so it never receives credentials. Even so, bind the opencode
  server to localhost and set `OPENCODE_SERVER_PASSWORD` if you expose it, since
  anything else on that port could read the keys.
- **Panelists can browse the web** (research mode, opencode backend: `webfetch` and
  `websearch`). They run with mutation tools denied (`bash`/`edit`/`write` are off) by
  default. Setting `OPENPRISM_PANEL_TOOLS=all` re-enables `bash`/`edit`/`write` for
  panelists. Only do that if you accept that several model agents will then be able to
  run commands and modify files on your machine.
- **Prompts and panel answers** go to whichever providers/models you select (directly,
  or via opencode). OpenPrism adds no telemetry and phones home to nothing; everything
  runs locally.

## Other notes

- **Autospawned opencode inherits OpenPrism's environment.** When OpenPrism starts its
  own `opencode serve`, that child inherits the parent environment, which may include
  provider keys loaded from `.env`. This is intentional, since opencode needs its own
  provider env, but it does mean those vars are in scope for the spawned server.
- **Remote opencode URLs.** `OPENPRISM_OPENCODE_URL` is used as-is (the scheme is
  checked to be http or https). Point it only at a server you trust, since prompts and,
  if you set `OPENCODE_SERVER_PASSWORD`, that credential go to it.

## Secrets hygiene

Keep `.env` and `providers.json` out of version control (both are in `.gitignore`).
Use `openprism doctor` to confirm your setup without printing keys.
