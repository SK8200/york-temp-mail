# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-08-22

First tagged release. ManyMail has been running in production since April 2026; this is the
point where the feature set and the deployment story are stable enough to pin a version to.

### Mail service — FastAPI + aiosmtpd

- SMTP receiver on port 25 for any domain pointed at the host, with optional STARTTLS
- DuckMail-compatible REST API on port 8080, so existing disposable-mail scripts work unchanged
- Multiple domains from one instance, with prefixes created on demand for catch-all use
- Message retention through `MESSAGE_TTL_DAYS`, or kept indefinitely
- Abuse controls: per-IP and per-sender rate limits, recipient and message size caps,
  IP and sender blacklists, optional greylisting

### Webmail viewer — Flask

- Search, read, reply, reply-all, forward, and compose with attachments
- Mail HTML passes an allowlist sanitizer; `<style>` blocks are rewritten against a CSS
  allowlist that blocks `url()`, `@import`, and script protocols
- Remote images load through a proxy that refuses private and link-local addresses
- Verification codes extracted from incoming mail, one click to copy
- Inbox, sent, and trash with soft delete, restore, and batch actions
- Attachment download and `.eml` export where the upstream API provides it
- Responsive layout with a master-detail drill-down on phones
- Chinese and English interface

### IMAP

- IMAP4rev1 server on port 993 backed by MongoDB, for Thunderbird and phone clients
- Optional bridge that pulls in external Gmail, Outlook, QQ, and 163 accounts

### Deployment

- One `docker compose up` brings up FastAPI, Flask, Node.js, and MongoDB
- MX, SPF, DKIM, and DMARC records documented in the README
- Production hardening guide in `docs/production-hardening.md`
- CI runs Ruff, Python tests, Node tests, and a Docker build on every push

[1.0.0]: https://github.com/margbug01/ManyMail/releases/tag/v1.0.0
