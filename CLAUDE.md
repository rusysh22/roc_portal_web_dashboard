# CLAUDE.md — Project Context for AI Assistants

> **Tujuan file ini**: Menjaga "kesadaran" / context AI lintas sesi. Setiap sesi baru, AI assistant (Claude Code) akan otomatis membaca file ini sebelum bekerja. Update file ini bila ada keputusan arsitektural baru, bukan untuk progress harian (gunakan PROGRESS.md untuk progress).

---

## 1. Project Identity

- **Nama**: ROC Portal Power BI
- **Owner**: rusydani.sh@gmail.com
- **Working dir**: `/home/ubuntu/roc_portal_power_bi`
- **Bahasa komunikasi default**: Bahasa Indonesia (campur teknis EN OK)
- **Dokumen kunci**: `PRD.md` (v1.1.0, source of truth)

## 2. What we're building (one-liner)

Secure web portal yang **embed report Power BI** ke end-user **tanpa** memberikan license PBI individual, dengan **RBAC dinamis**, **multi-tenant**, **bilingual ID/EN**, dan token PBI **tidak pernah bocor** ke client (anti Inspect Element).

## 3. Non-negotiable Constraints

1. **Embed token & embed URL Power BI TIDAK boleh muncul di server-rendered HTML.** Selalu via XHR ke endpoint authenticated. Token hanya hidup di JS closure, bukan localStorage.
2. **Service Principal** (bukan master account user/password) untuk auth ke Power BI.
3. **Multi-tenant**: hampir semua tabel data harus punya `tenant_id`. Middleware tenant resolver wajib di setiap request. Query auto-scoped.
4. **Public internet exposure**: TLS valid wajib, security headers ketat (CSP, HSTS), rate limit, fail2ban-friendly logs.
5. **Docker port non-standar**: app `7788`, Nginx HTTPS `7789`, HTTP `7780`. JANGAN pakai 8000/80/443.
6. **Bilingual ID/EN**: setiap string user-facing harus pakai i18n key, jangan hardcode.
7. **No emoji** di kode/UI kecuali user explicit minta. Ikon pakai Lucide/Heroicons.

## 4. Tech Stack (locked)

| Layer | Tool |
|---|---|
| Backend | FastAPI 0.115+, Python 3.12 |
| ORM | SQLAlchemy 2.x + Alembic |
| DB | PostgreSQL 16 |
| Cache/queue | Redis 7 |
| Auth | JWT (HS256) di httpOnly Secure SameSite=Strict cookie |
| Frontend | Jinja2 SSR + Tailwind CSS 3 + Alpine.js + HTMX |
| i18n | Babel + JSON catalog (id.json, en.json) |
| PBI client | powerbi-client-python (backend) + powerbi-client.js (frontend, served via CDN cdn.powerbi.com) |
| Reverse proxy | Nginx (TLS termination, security headers) |
| Container | Docker Compose |

## 5. Project Structure (target)

```
roc_portal_power_bi/
├── PRD.md                          # source of truth
├── CLAUDE.md                       # this file
├── PROGRESS.md                     # work log
├── docker-compose.yml
├── .env.example
├── .gitignore
├── nginx/
│   ├── Dockerfile
│   └── nginx.conf
└── app/
    ├── Dockerfile
    ├── pyproject.toml
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── package.json                # for tailwind build only
    ├── alembic.ini
    ├── alembic/
    └── src/
        ├── main.py                 # FastAPI app factory
        ├── config.py               # Pydantic settings from env
        ├── deps.py                 # DI: db, redis, current_user, current_tenant
        ├── i18n.py                 # locale loader & translate fn
        ├── core/
        │   ├── security.py         # JWT, bcrypt, CSRF
        │   ├── rbac.py             # require_permission decorator
        │   ├── tenant.py           # TenantResolver middleware
        │   ├── powerbi.py          # SP token, embed token, export
        │   └── audit.py
        ├── models/                 # SQLAlchemy models (all tenant-scoped)
        ├── schemas/                # Pydantic
        ├── api/                    # JSON API routers
        ├── views/                  # Jinja2 HTML routers
        ├── templates/
        │   ├── base.html
        │   ├── auth/
        │   ├── viewer/
        │   └── admin/
        ├── static/
        │   ├── css/                # tailwind output -> app.css
        │   ├── src/css/            # tailwind input
        │   ├── js/
        │   └── img/
        ├── locales/
        │   ├── id.json
        │   └── en.json
        └── tests/
```

## 6. Coding Standards

- **Linting/format**: ruff (line len 100), black, mypy strict on `core/` and `models/`.
- **Type hints**: wajib di semua public function.
- **Pydantic v2** for schemas. SQLAlchemy v2 typed mapped style.
- **No SQL string concatenation** — pakai SQLAlchemy ORM/core only.
- **Logging**: structured JSON (`structlog`), level INFO default, DEBUG via env.
- **Tests**: pytest + httpx AsyncClient, fixtures untuk tenant/user/db.
- **Commit message**: Conventional Commits (feat:, fix:, chore:, docs:).
- **Branch**: `main` (stable), `develop` (integration), feature `feat/<phase>-<topic>`.

## 7. Conventions Spesifik

### 7.1. Tenant scoping
Semua model class extend `TenantScopedBase` yang punya `tenant_id` + foreign key ke `tenants`. Repository pattern: function selalu terima `tenant_id` sebagai arg pertama.

### 7.2. Permission codes
Format: `<resource>.<action>`. Contoh: `user.manage`, `report.view`, `report.export`, `config.edit`, `audit.view`. Permission `*` = super admin only (lintas tenant).

### 7.3. i18n key naming
Format: `<domain>.<page>.<element>`. Contoh: `auth.login.title`, `report.viewer.export_button`. Key gak boleh kalimat panjang.

### 7.4. Power BI token caching key
Redis: `pbi:aad_token:{tenant_id}:default` (jika SP per-tenant) atau `pbi:aad_token:global` (jika SP global). Default v1: **SP global**, multi-tenant pakai workspace berbeda di tenant Azure yang sama.

### 7.5. Audit log
Tiap action sensitif harus emit `audit.log(user, action, target, metadata)`. Format action: `<verb>.<resource>` ex: `view.report`, `update.user`, `login.success`, `login.fail`.

## 8. Decisions Made (do not re-debate)

- ✅ Service Principal, bukan master account
- ✅ SSR (Jinja2) bukan SPA, alasan: lebih aman by default, lebih cepat ship, sesuai skala 200 concurrent user
- ✅ Multi-tenant single-DB (shared schema dengan tenant_id), bukan database-per-tenant
- ✅ JWT di httpOnly cookie, bukan Authorization header (lebih aman dari XSS, butuh CSRF token)
- ✅ Bilingual ID + EN, default ID
- ✅ Port 7788 (app), 7789 (HTTPS), 7780 (HTTP redirect)
- ✅ PostgreSQL bukan MySQL (JSONB lebih kaya, RLS di-DB jika nanti perlu)
- ❌ TIDAK pakai Celery di v1 (BackgroundTasks FastAPI cukup); Celery masuk jika export jadi bottleneck

## 9. Things to Ask User Before Doing

- Mau pakai domain apa di production? (untuk subdomain-based tenant resolution)
- Sertifikat TLS: Let's Encrypt auto via Caddy/Traefik, atau manual upload?
- SMTP provider untuk email forgot-password? (Sendgrid, Mailgun, AWS SES, atau Gmail SMTP)
- Logo / brand guideline default tenant?

## 10. How to use this file

- **Setiap sesi baru**, baca file ini dulu sebelum bekerja.
- **Sebelum nulis kode**, cek apakah keputusan yang akan kamu buat sudah ada di section 8. Kalau bertentangan, JANGAN ubah tanpa konfirmasi user.
- **Update file ini** hanya saat ada keputusan arsitektural baru (bukan progress).
- **PROGRESS.md** untuk log harian / per-phase progress.
