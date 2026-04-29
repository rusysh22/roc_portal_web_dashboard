# ROC Portal Power BI

Secure web portal untuk embedding Power BI report dengan RBAC dinamis, multi-tenant, dan bilingual ID/EN. Token Power BI tidak pernah ter-ekspos ke client.

> **Source of truth**: lihat `PRD.md` untuk requirement detail dan `CLAUDE.md` untuk konteks development.
> **Progress log**: lihat `PROGRESS.md`.

## Quick Start (Development)

### 1. Clone & setup env
```bash
cp .env.example .env
# Edit .env, minimal isi: APP_SECRET_KEY, POSTGRES_PASSWORD
```

### 2. Build & run
```bash
docker compose up --build
```

### 3. Akses
- Public HTTPS: <https://localhost:7789> (sertifikat self-signed dev — accept warning di browser)
- Health check: `https://localhost:7789/healthz`
- HTTP redirect: `http://localhost:7780` → 301 ke HTTPS

> **Port**: app `7788` (internal), Nginx HTTPS `7789`, HTTP redirect `7780`. Port non-standar by design (lihat CLAUDE.md §3.5).

## Stack

| Layer | Tool |
|---|---|
| Backend | FastAPI 0.115+ / Python 3.12 |
| ORM | SQLAlchemy 2.x + Alembic |
| DB | PostgreSQL 16 |
| Cache | Redis 7 |
| Frontend | Jinja2 SSR + Tailwind CSS 3 + Alpine.js + HTMX |
| i18n | Babel + JSON catalog (id, en) |
| Reverse proxy | Nginx (TLS termination) |

## Project Structure

```
.
├── PRD.md                  # Product Requirements Document
├── CLAUDE.md               # Project context (for AI assistant)
├── PROGRESS.md             # Work log
├── docker-compose.yml
├── .env.example
├── nginx/                  # Reverse proxy + TLS
└── app/
    ├── Dockerfile
    ├── pyproject.toml
    ├── tailwind.config.js
    ├── alembic/
    └── src/
        ├── main.py         # FastAPI app
        ├── config.py
        ├── i18n.py
        ├── core/           # Security, RBAC, tenancy, Power BI
        ├── models/         # SQLAlchemy models
        ├── schemas/        # Pydantic
        ├── api/            # JSON API
        ├── views/          # Jinja2 HTML
        ├── templates/
        ├── static/
        ├── locales/        # id.json, en.json
        └── tests/
```

## Development Phases

Lihat `PRD.md §16` untuk roadmap penuh. Status: **Phase 0 (Scaffold) — DONE**.

## Security Highlights

- Power BI Service Principal (bukan master account)
- Embed token short-lived, di-fetch lewat XHR (tidak pernah di SSR HTML)
- JWT di httpOnly Secure SameSite=Strict cookie
- CSP ketat, HSTS, X-Frame-Options
- Rate limit di Nginx + slowapi (per-user via Redis)
- bcrypt cost 12, account lockout, optional 2FA TOTP
