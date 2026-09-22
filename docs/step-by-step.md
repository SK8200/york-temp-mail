# ManyMail — Full Step-by-Step Guide

This document walks through every step: start the stack, open the UI, create a mailbox, receive mail, store it, and read it in the browser.

The frontend is **HTML + inline CSS/JS** served by Flask. There is no React/Vue/Next build.

---

## 1. What runs where

One `docker compose` file starts five services:

| Service | Container | Port | Role |
|---|---|---|---|
| **mongodb** | `mail-mongodb` | internal `27017` | Stores accounts, domains, messages |
| **mail-service** | `mail-service` | SMTP `25` (or `2525` locally), API `8080` | Receives SMTP, REST API |
| **mail-viewer** | `mail-viewer` | `5000` | Web UI (HTML) |
| **imap-mail** | `mail-imap-bridge` | internal `3939` | External IMAP (Gmail/Outlook) |
| **imap-server** | `mail-imap-server` | `993` | IMAP for desktop/phone clients |

Flow:

```
Sender  --SMTP-->  mail-service  --insert-->  MongoDB (mailserver.messages)
Browser --HTTP-->  mail-viewer   --API----->  mail-service  --read-->  MongoDB
```

---

## 2. Configure

```bash
cp .env.example .env
```

Important keys in `.env`:

| Key | What it does |
|---|---|
| `DOMAINS` | Domains this server accepts, e.g. `yourdomain.com` |
| `UNIFIED_PASSWORD` | Password used for every auto-created mailbox |
| `ACCESS_PASSWORD` | Viewer login. **Empty = no login page.** Set a value to show login. |
| `AUTO_CREATE_ACCOUNTS` | `1` = Query creates the mailbox if it does not exist |
| `DUCKMAIL_API_KEY` | Must match `API_KEY` so the viewer can create mailboxes / manage domains |
| `MESSAGE_TTL_DAYS` | Messages are deleted after N days (`3` by default) |
| `DB_NAME` | MongoDB database name (`mailserver`) |

This local setup uses `DOMAINS=yourdomain.com` and `AUTO_CREATE_ACCOUNTS=1`.

---

## 3. Start the stack

```bash
docker compose up -d
docker compose ps
curl http://127.0.0.1:8080/health
```

Open the UI: [http://127.0.0.1:5000](http://127.0.0.1:5000)

**Port 25 conflict:** if another container already binds SMTP 25 (for example CloakMail), ManyMail SMTP is published on **2525** instead. The API on `8080` and UI on `5000` are unchanged.

```bash
# Recreate only the web UI after HTML/API edits
docker compose up -d --no-deps --build mail-viewer
```

---

## 4. Open the frontend

The UI is not a Node app. Flask renders HTML templates.

| File | What it is |
|---|---|
| `mail-viewer/templates/index.html` | Inbox, compose, settings (main UI) |
| `mail-viewer/templates/login.html` | Login page |
| `mail-viewer/app.py` | Routes and `/api/...` the HTML calls |
| `mail-viewer/imap-mail-app/public/index.html` | IMAP tab (iframe) |

After you edit a template:

```bash
docker compose up -d --no-deps --build mail-viewer
```

Then refresh the browser.

---

## 5. Login (optional)

1. Browser hits `/`.
2. If `ACCESS_PASSWORD` is **empty**, `/login` redirects to the inbox. No password screen.
3. If `ACCESS_PASSWORD` is **set**, you must enter that password. Session cookie `authenticated` is stored.
4. APIs are wrapped with `@login_required` only when a password is configured.

`/logout` clears the session. With no password it goes back to the inbox.

---

## 6. Query / create a mailbox

On the inbox page:

1. Pick a domain (`yourdomain.com`).
2. Type a prefix, e.g. `sfsfgfef`.
3. Click **Query**.

What happens:

1. Browser `POST /api/inbox/query` with `email=sfsfgfef@yourdomain.com`.
2. Viewer tries `POST http://mail-service:8080/token` using `UNIFIED_PASSWORD`.
3. If login fails and `AUTO_CREATE_ACCOUNTS=1`:
   - `POST /accounts` creates the mailbox in MongoDB `accounts`.
   - Viewer logs in again and loads messages.
4. If auto-create is `0`, you see: *Mailbox not found or password incorrect. Auto-create is disabled.*

The mailbox address is `{prefix}@{domain}`.

---

## 7. Receive an email (SMTP)

Internet (or a local test) sends SMTP to ManyMail.

**On this machine SMTP is `127.0.0.1:2525`.**

1. Client connects and sends `MAIL FROM`, `RCPT TO`, `DATA`.
2. `MailHandler` in `mail-service/app.py` checks:
   - recipient syntax
   - domain is in `get_active_domains()` (MongoDB `domains`)
   - size / rate limits
3. The raw message is parsed (From, To, Subject, text, HTML, attachments).
4. A document is inserted into MongoDB.

Send a test message:

```python
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

to_addr = "sfsfgfef@yourdomain.com"
msg = MIMEMultipart("alternative")
msg["From"] = "Acme Security <noreply@acme.example>"
msg["To"] = to_addr
msg["Subject"] = "Your verification code is 719304"
msg.attach(MIMEText("Your verification code is 719304", "plain", "utf-8"))
msg.attach(MIMEText("<h1>Verify your email</h1><p>719304</p>", "html", "utf-8"))

with smtplib.SMTP("127.0.0.1", 2525, timeout=10) as smtp:
    smtp.sendmail(msg["From"], [to_addr], msg.as_string())
```

For a real domain, point MX to this server and use port **25** (not 2525).

---

## 8. Where the email is stored

**MongoDB**, not files and not the HTML templates.

| Item | Value |
|---|---|
| Container | `mail-mongodb` |
| Docker volume | `mongo_data` → `/data/db` |
| Database | `mailserver` |
| Collection | `messages` |

Insert happens here: `mail-service/app.py` → `db.messages.insert_one(doc)`.

Document fields:

- `from` — `{ address, name }`
- `to` / `to_addresses`
- `subject`, `intro`, `text`, `html`
- `attachments` (binary in the same document)
- `seen`, `is_deleted`
- `created_at`, `updated_at`
- `size`

Other collections:

| Collection | Stores |
|---|---|
| `accounts` | Mailboxes |
| `domains` | Allowed domains |
| `sent_messages` | Mail sent from the compose UI |

Inspect:

```bash
docker exec -it mail-mongodb mongosh mailserver --eval \
  'db.messages.find().sort({created_at:-1}).limit(2).pretty()'
```

Messages expire after `MESSAGE_TTL_DAYS` (default 3).

External IMAP accounts (Gmail/Outlook tab) use a different volume: `imap_mail_data`.

---

## 9. How the UI shows the email

1. Inbox query returns the message list (no full HTML body).
2. Click a row → `viewMailDetail()` → `POST /api/inbox/detail`.
3. Viewer loads the message from mail-service, sanitizes HTML (`bleach`), extracts a 6-digit code if present.
4. The body is written into a sandboxed iframe (`_renderMailBodyIframe` in `index.html`).

What you see:

- **List:** sender, subject, preview, time, green code badge
- **Detail:** From / To / Subject / Time / Code, then the HTML body
- Actions: Reply, Reply all, Forward, Plain text, Download `.eml`, Delete

---

## 10. Compose / send (outgoing)

Compose in the UI calls `POST /api/send`.

Outgoing mail is **not** SMTP from this box by default. It uses **Resend** if `RESEND_API_KEY` is set. A copy is stored in `sent_messages` via `/admin/sent`.

Without `RESEND_API_KEY`, send fails with: *Resend API key is not configured*.

---

## 11. Other UI tabs

| Tab | What it does |
|---|---|
| **Inbox** | Local ManyMail mailboxes |
| **Sent** | Messages sent through Resend |
| **Trash** | Soft-deleted mail (`is_deleted: true`) |
| **IMAP** | Connect Gmail / Outlook / QQ / 163 (iframe → `/imap/`) |
| **Settings** | Domain list (add / disable) |

---

## 12. REST API (mail-service, port 8080)

Base URL: `http://127.0.0.1:8080`

```bash
# Create mailbox
curl -X POST http://127.0.0.1:8080/accounts \
  -H "Content-Type: application/json" \
  -d '{"address":"user@yourdomain.com","password":"shared-mailbox-password"}'

# Login
TOKEN=$(curl -s -X POST http://127.0.0.1:8080/token \
  -H "Content-Type: application/json" \
  -d '{"address":"user@yourdomain.com","password":"shared-mailbox-password"}' \
  | jq -r '.token')

# List mail
curl http://127.0.0.1:8080/messages \
  -H "Authorization: Bearer $TOKEN"
```

Viewer APIs (port 5000, used by the HTML):

- `POST /api/inbox/query`
- `POST /api/inbox/detail`
- `POST /api/inbox/search`
- `POST /api/inbox/delete`
- `POST /api/send`
- `GET /api/domains`

---

## 13. End-to-end checklist

1. `docker compose up -d` — all containers healthy.
2. Open `http://127.0.0.1:5000`.
3. Query prefix `sfsfgfef` on `yourdomain.com` (mailbox is created).
4. Send SMTP to `sfsfgfef@yourdomain.com` on port `2525`.
5. Message lands in MongoDB `mailserver.messages`.
6. Click **Query** (or wait for Auto refresh).
7. Click the row — HTML body appears in Mail Detail.

---

## 14. File map

```
ManyMail/
├── docker-compose.yml          # All services + ports
├── .env                        # Local config
├── mail-service/app.py         # SMTP receive + REST + Mongo writes
├── mail-viewer/
│   ├── app.py                  # Flask UI backend
│   └── templates/
│       ├── index.html          # Main frontend (start here)
│       └── login.html
├── mail-viewer/imap-mail-app/  # IMAP tab
├── imap-server/                # IMAP :993
└── docs/step-by-step.md        # This file
```
