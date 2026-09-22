# Contributing

Thanks for looking. Bug reports, docs fixes, and patches are all welcome.

For anything security-related, go through [SECURITY.md](SECURITY.md) instead of a public issue.

## Layout

| Path | What runs there |
|:-----|:----------------|
| `mail-service/` | FastAPI + aiosmtpd — SMTP receiver on `:25`, REST API on `:8080` |
| `mail-viewer/` | Flask webmail UI on `:5000` |
| `mail-viewer/imap-mail-app/` | Node.js IMAP bridge on `:3939` |
| `imap-server/` | Node.js IMAP server on `:993` |
| `tools/` | operational scripts |
| `docs/` | documentation and the GitHub Pages landing page |

## Running it

```bash
cp .env.example .env      # fill in the secrets before anything else
docker compose up -d --build
docker compose logs -f
```

To iterate on the webmail UI alone, skip Docker:

```bash
cd mail-viewer
pip install -r requirements.txt
SECRET_KEY=dev ACCESS_PASSWORD= PORT=5000 python app.py
```

`ACCESS_PASSWORD=` empty hides the login page and opens the inbox directly.

## Tests and lint

Same commands CI runs, so run them before opening a PR:

```bash
# lint
ruff check mail-service/ mail-viewer/app.py mail-viewer/tests/ tools/

# Python tests
cd mail-service && pytest tests/ -v && cd ..
pytest mail-viewer/tests/ -v

# Node tests
cd mail-viewer/imap-mail-app && npm ci && npm test && cd ../..
cd imap-server && npm ci && npm test && cd ..
```

Ruff config lives in `ruff.toml`: `py311`, line length 120.

## Pull requests

- One topic per PR.
- Say what breaks if the change is wrong, and how you checked that it does not.
- Add a test when you fix a bug. `mail-viewer/tests/test_app.py` shows the pattern for loading the Flask app under a controlled environment.
- Keep the existing style of the file you are editing. The frontend lives in one `mail-viewer/templates/index.html`; follow the conventions already there rather than introducing a build step.
- User-facing strings in the viewer need both `zh` and `en` entries in the `LANGS` object.
- Touching the mail HTML sanitizer means adding a test that proves the payload no longer gets through.

## Reporting a bug

Open an issue with the component, the commit, what you expected, and what happened. Logs from `docker compose logs <service>` help more than a description of the logs.
