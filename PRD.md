# Product Requirements Document (PRD)
## ROC Portal — Power BI Secure Embed Portal

| Field | Value |
|---|---|
| **Project Name** | ROC Portal Power BI |
| **Version** | 1.0.0 |
| **Date** | 2026-04-28 |
| **Owner** | rusydani.sh@gmail.com |
| **Status** | Draft |

---

## 1. Executive Summary

ROC Portal adalah aplikasi web internal yang berfungsi sebagai **secure gateway** untuk mendistribusikan report Microsoft Power BI ke pengguna akhir tanpa perlu memberikan license Power BI individual. Portal ini menggunakan pola **"Embed for your customers" (App Owns Data)** dengan satu Service Principal sebagai pemilik akses Power BI, kemudian mengontrol siapa boleh melihat report apa melalui sistem **Role-Based Access Control (RBAC)** yang dinamis dan dapat dikonfigurasi via UI admin.

### 1.1. Problem Statement
- License Power BI Pro per user mahal jika di-roll-out ke banyak viewer.
- Sharing report langsung dari Power BI Service tidak fleksibel untuk audience non-organisasi atau user dengan akses terkontrol.
- Akses langsung ke Power BI workspace berisiko (user bisa explore report lain atau download data).
- Kebutuhan branding & menu yang dinamis tidak bisa dipenuhi Power BI Service standar.

### 1.2. Goals
- Embed report Power BI di portal web dengan **token short-lived** di sisi backend.
- **Zero exposure** terhadap embed URL/token saat user melakukan Inspect Element.
- RBAC dinamis (admin bisa CRUD user, role, permission, menu, report mapping tanpa redeploy).
- Site Configuration dinamis (logo, nama portal, warna, session timeout, dll).
- Deploy via Docker dengan port non-standar (`7788`).
- UI modern, interaktif, responsif (Tailwind CSS).

### 1.3. Non-Goals
- Bukan menggantikan Power BI Service untuk content creator / data analyst.
- Tidak melakukan ETL atau pembuatan dataset.
- Tidak mendukung edit report via portal (read-only viewer).

---

## 2. Stakeholders & User Personas

| Persona | Deskripsi | Kebutuhan Utama |
|---|---|---|
| **Super Admin** | Pengelola portal, IT/Data team | Manage user, role, report config, site config, audit log |
| **Admin** | Manajer departemen | Manage user di lingkup departemen, assign role |
| **Viewer** | End user (karyawan, klien, partner) | Login, lihat menu, lihat report yang di-assign |
| **Auditor** | Compliance/security team | Akses read-only ke audit log |

---

## 3. Architecture Overview

### 3.1. High-Level Architecture

```
┌────────────┐   HTTPS    ┌──────────────┐    ┌───────────────────┐
│   Browser  │◄──────────►│    Nginx     │◄──►│  FastAPI (7788)   │
│  (User)    │            │  (TLS, CSP)  │    │  + Jinja2 + HTMX  │
└────────────┘            └──────────────┘    └─────────┬─────────┘
                                                        │
                                ┌───────────────────────┼───────────────────────┐
                                │                       │                       │
                          ┌─────▼─────┐         ┌───────▼───────┐       ┌───────▼────────┐
                          │ Postgres  │         │     Redis     │       │  Power BI API  │
                          │ (RBAC,    │         │ (Token cache, │       │ (Service       │
                          │ configs,  │         │  rate limit,  │       │  Principal,    │
                          │ audit)    │         │  sessions)    │       │  Azure AD)     │
                          └───────────┘         └───────────────┘       └────────────────┘
```

### 3.2. Tech Stack

| Layer | Choice | Reason |
|---|---|---|
| Backend | **FastAPI (Python 3.12)** | Async, type-safe, OpenAPI native |
| ORM | **SQLAlchemy 2.x + Alembic** | Mature, migration-ready |
| Database | **PostgreSQL 16** | Reliable, ACID, JSON support |
| Cache | **Redis 7** | Token cache, rate limit, session |
| Auth | **JWT** in httpOnly Secure SameSite=Strict cookie | Prevent XSS token theft |
| Frontend | **Jinja2 SSR + Tailwind CSS + Alpine.js + HTMX** | Lightweight, secure-by-default, interaktif tanpa SPA overhead |
| Icons | **Lucide / Heroicons** | Modern SVG icons |
| Charts (admin dashboard) | **Chart.js** | Native untuk dashboard internal portal |
| Power BI SDK | **powerbi-client-python** + `powerbi-client.js` (frontend) | Official MS SDK |
| Reverse Proxy | **Nginx** | TLS termination, security headers |
| Container | **Docker + Docker Compose** | Reproducible deploy |
| **Port (App)** | **7788** | Non-standar, mudah diingat |
| **Port (Nginx HTTPS)** | **7789** | Public-facing TLS |

### 3.3. Why Service Principal (bukan master account)?
- Tidak kena MFA enforcement.
- Token lebih clean (client_credentials flow).
- Bisa di-rotate via Azure tanpa ganggu user lain.
- Audit Azure AD lebih jelas.
- **Requirement Azure**: Service Principal harus di-add sebagai **Member** workspace Power BI dan tenant setting "Service principals can use Power BI APIs" harus enabled.

---

## 4. Functional Requirements

### 4.1. Authentication
- **F-AUTH-1** Login form (email + password), bcrypt-hashed password.
- **F-AUTH-2** JWT access token (15 menit) + refresh token (7 hari, rotating) di httpOnly cookie.
- **F-AUTH-3** Logout — invalidate refresh token (Redis blacklist).
- **F-AUTH-4** Optional 2FA (TOTP, RFC 6238) untuk role Admin & Super Admin.
- **F-AUTH-5** Password policy: min 12 char, mixed case, angka, simbol.
- **F-AUTH-6** Account lockout setelah 5 gagal login (15 menit).
- **F-AUTH-7** Forgot password via email magic link (token expire 30 menit).

### 4.2. Authorization (RBAC)
- **F-RBAC-1** Skema:
  - `users (id, email, name, password_hash, is_active, two_fa_secret, ...)`
  - `roles (id, name, description)`
  - `permissions (id, code, description)` — contoh: `report.view`, `user.manage`, `config.edit`
  - `user_roles (user_id, role_id)`
  - `role_permissions (role_id, permission_id)`
  - `report_role_access (report_id, role_id)`
  - `menu_items (id, label, icon, url, parent_id, order, required_permission, is_active)`
- **F-RBAC-2** Decorator `@require_permission("report.view")` di backend route.
- **F-RBAC-3** Menu di-render server-side berdasarkan permission user (item tanpa permission tidak ter-render di HTML sama sekali).
- **F-RBAC-4** Admin UI untuk CRUD role, permission, assignment.

### 4.3. Power BI Embed Flow
- **F-PBI-1** Backend menyimpan kredensial Service Principal di **environment variable** (`AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`), TIDAK di DB.
- **F-PBI-2** Backend cache **AAD access token** di Redis dengan TTL = `expires_in - 5 menit`.
- **F-PBI-3** Endpoint `GET /api/embed/{report_slug}`:
  1. Cek user login & punya permission `report.view` & ada di `report_role_access`.
  2. Generate **embed token** via Power BI REST `GenerateTokenInGroup` dengan:
     - `accessLevel: View`
     - `effectiveIdentity` (jika report pakai RLS): username = user.email, roles = mapping dari user role.
     - `lifetimeInMinutes: 60`
  3. Return JSON: `{ embedUrl, embedToken, reportId, expiry }`.
  4. Audit log: user X request embed report Y at timestamp Z.
- **F-PBI-4** Frontend hanya panggil `/api/embed/{slug}` setelah halaman load, token disimpan di **closure JS variable**, bukan global/localStorage.
- **F-PBI-5** Auto-refresh embed token sebelum expire (di sisi JS, panggil ulang endpoint).
- **F-PBI-6** Rate limit endpoint: 30 request / menit / user.
- **F-PBI-7** Watermark dinamis (email user + timestamp) di-overlay di atas iframe via CSS.

### 4.4. Report Management (Admin)
- **F-RPT-1** CRUD report: `id, slug, name, description, workspace_id, report_id, dataset_id, is_rls, rls_role_mapping (json), is_active`.
- **F-RPT-2** Test connection button (admin click → backend coba generate token).
- **F-RPT-3** Assign report ke role(s).
- **F-RPT-4** Soft delete (set `is_active = false`).

### 4.5. Menu Management
- **F-MENU-1** Tree menu (max 2 level), drag-drop reorder.
- **F-MENU-2** Field: `label, icon (lucide name), url (internal route or report slug), required_permission`.
- **F-MENU-3** Preview live di sidebar admin.

### 4.6. User Management
- **F-USR-1** CRUD user, assign multiple roles.
- **F-USR-2** Bulk import CSV (email, name, role).
- **F-USR-3** Force password reset on next login.
- **F-USR-4** Activate / deactivate user.

### 4.7. Site Configuration (Dynamic)
Disimpan di tabel `site_config (key, value, value_type, description)` — JSON-typed, di-cache Redis, invalidate on write.

| Key | Type | Default | Deskripsi |
|---|---|---|---|
| `site.name` | string | "ROC Portal" | Nama portal di header & title |
| `site.logo_url` | string | `/static/logo.svg` | Logo (upload via admin) |
| `site.favicon_url` | string | `/static/favicon.ico` | |
| `site.primary_color` | string | `#0ea5e9` | Tailwind CSS variable |
| `site.secondary_color` | string | `#1e293b` | |
| `site.footer_text` | string | "© 2026 ROC" | |
| `site.login_bg_url` | string | — | Background image login page |
| `auth.session_timeout_min` | int | 60 | Idle timeout |
| `auth.password_min_len` | int | 12 | |
| `auth.lockout_threshold` | int | 5 | |
| `auth.lockout_duration_min` | int | 15 | |
| `auth.enable_2fa_admin` | bool | true | |
| `pbi.token_lifetime_min` | int | 60 | Embed token lifetime |
| `pbi.watermark_enabled` | bool | true | |
| `pbi.watermark_template` | string | `{{user.email}} • {{now}}` | |
| `feature.audit_log_enabled` | bool | true | |
| `feature.allow_export` | bool | false | Apakah user boleh export report |

### 4.8. Audit Log
- **F-AUD-1** Catat: login success/fail, logout, embed request, admin CRUD, config change.
- **F-AUD-2** Field: `id, timestamp, user_id, ip, user_agent, action, target_type, target_id, metadata (json), result`.
- **F-AUD-3** UI filter & export CSV (Super Admin / Auditor only).
- **F-AUD-4** Retensi 1 tahun, archive otomatis ke object storage opsional.

### 4.9. Dashboard (Landing setelah login)
- Welcome message dinamis.
- Quick access card untuk report yang user punya akses.
- "Recently viewed" (dari audit log).
- Notifikasi/announcement (di-set admin via site config).

---

## 5. Non-Functional Requirements

### 5.1. Security (CRITICAL)
- **S-1** **Embed token & URL** TIDAK PERNAH dikirim ke browser di server-rendered HTML — selalu via fetch ke endpoint authenticated.
- **S-2** **Content Security Policy** ketat:
  ```
  default-src 'self';
  script-src 'self' https://cdn.powerbi.com 'unsafe-inline';
  frame-src https://app.powerbi.com https://*.powerbi.com;
  style-src 'self' 'unsafe-inline';
  img-src 'self' data: https:;
  connect-src 'self' https://api.powerbi.com;
  ```
- **S-3** Headers wajib: `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy`.
- **S-4** CSRF token (double-submit cookie) untuk semua state-changing request.
- **S-5** Rate limiting (Redis-based) per IP & per user.
- **S-6** Input validation via Pydantic schema.
- **S-7** SQL injection: pakai SQLAlchemy parameterized query exclusively.
- **S-8** Secret management: env var via `.env` (gitignored) atau Docker secret di production.
- **S-9** TLS only (Nginx redirect HTTP→HTTPS), self-signed sertifikat untuk dev, Let's Encrypt untuk prod.
- **S-10** Password hashing: **bcrypt cost 12** atau **argon2id**.
- **S-11** Session fixation prevention: regenerate session ID on login.
- **S-12** Disable directory listing, hide server header.

### 5.2. Performance
- **P-1** Login response < 500ms (P95).
- **P-2** Embed token endpoint < 800ms (P95) — cache AAD token, generate embed token fresh.
- **P-3** Concurrent user target: 200.
- **P-4** Page load (TTFB) < 300ms.

### 5.3. Reliability
- **R-1** Health check `/healthz` (DB + Redis + PBI API ping).
- **R-2** Graceful shutdown (close DB pool, finish in-flight req).
- **R-3** Auto-restart container on failure (Docker `restart: unless-stopped`).

### 5.4. Maintainability
- **M-1** Test coverage backend ≥ 75% (pytest).
- **M-2** Pre-commit: ruff, black, mypy.
- **M-3** Structured logging (JSON) → stdout, dikoleksi Docker log driver.

### 5.5. Usability
- **U-1** Responsive (mobile, tablet, desktop) via Tailwind.
- **U-2** Dark mode toggle (preference disimpan di cookie).
- **U-3** Loading skeleton untuk report iframe.
- **U-4** Toast notification untuk action sukses/gagal.
- **U-5** Keyboard accessible (WCAG 2.1 AA).

---

## 6. Database Schema (Initial)

```sql
-- Core auth
users(id, email UNIQUE, name, password_hash, is_active, two_fa_secret, must_reset_pw, last_login_at, failed_attempts, locked_until, created_at, updated_at)
roles(id, name UNIQUE, description, is_system, created_at)
permissions(id, code UNIQUE, description)
user_roles(user_id FK, role_id FK, PK(user_id, role_id))
role_permissions(role_id FK, permission_id FK, PK(role_id, permission_id))

-- Power BI
reports(id, slug UNIQUE, name, description, workspace_id, report_id, dataset_id, is_rls, rls_config JSONB, is_active, created_at)
report_role_access(report_id FK, role_id FK, PK(report_id, role_id))

-- Menu
menu_items(id, parent_id FK NULL, label, icon, url, order_index, required_permission, is_active)

-- Configuration
site_config(key PK, value JSONB, value_type, description, updated_by FK, updated_at)

-- Audit
audit_logs(id, ts, user_id, ip, user_agent, action, target_type, target_id, metadata JSONB, result)

-- Sessions / refresh tokens (also in Redis but persistent fallback)
refresh_tokens(id, user_id FK, token_hash, expires_at, revoked_at, created_at)
```

---

## 7. API Endpoints (Initial)

| Method | Path | Auth | Deskripsi |
|---|---|---|---|
| POST | `/api/auth/login` | public | Login |
| POST | `/api/auth/logout` | user | Logout |
| POST | `/api/auth/refresh` | refresh cookie | Rotate token |
| POST | `/api/auth/forgot` | public | Send reset email |
| POST | `/api/auth/reset` | reset token | Reset password |
| POST | `/api/auth/2fa/setup` | user | TOTP enroll |
| POST | `/api/auth/2fa/verify` | user | TOTP verify |
| GET  | `/api/me` | user | Profile + permissions + menu |
| GET  | `/api/embed/{report_slug}` | `report.view` | Generate embed token |
| GET  | `/api/admin/users` | `user.manage` | List |
| POST | `/api/admin/users` | `user.manage` | Create |
| PUT  | `/api/admin/users/{id}` | `user.manage` | Update |
| DELETE | `/api/admin/users/{id}` | `user.manage` | Soft delete |
| ... | (idem untuk roles, permissions, reports, menu_items) | | |
| GET  | `/api/admin/config` | `config.edit` | Get all |
| PUT  | `/api/admin/config/{key}` | `config.edit` | Update |
| GET  | `/api/admin/audit` | `audit.view` | Filter & paginate |
| GET  | `/healthz` | public | Health check |

---

## 8. UI / Pages

### 8.1. Public
- `/login` — login form, branding dinamis
- `/forgot-password`, `/reset-password`

### 8.2. Authenticated (Viewer)
- `/` — dashboard (recent + quick access)
- `/reports/{slug}` — embed page (iframe + watermark)
- `/profile` — change password, 2FA setup

### 8.3. Admin
- `/admin/users`
- `/admin/roles`
- `/admin/permissions`
- `/admin/reports`
- `/admin/menu`
- `/admin/config` — site configuration
- `/admin/audit`
- `/admin/dashboard` — stats: active user, top viewed report, login trend (Chart.js)

### 8.4. Design System
- Layout: sidebar (collapsible) + topbar + main area
- Component: card, modal, drawer, table dengan pagination + filter, toast, dropdown
- Theme: gunakan CSS variable yang di-inject dari `site_config` (primary, secondary color)
- Font: Inter (default) atau dari config

---

## 9. Project Structure

```
roc_portal_power_bi/
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
├── nginx/
│   ├── Dockerfile
│   └── nginx.conf
├── app/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic/
│   ├── src/
│   │   ├── main.py
│   │   ├── config.py            # Pydantic settings
│   │   ├── deps.py              # DI: db, redis, current_user
│   │   ├── core/
│   │   │   ├── security.py      # JWT, bcrypt, CSRF
│   │   │   ├── rbac.py          # require_permission decorator
│   │   │   ├── powerbi.py       # Service Principal + embed token
│   │   │   └── audit.py
│   │   ├── models/              # SQLAlchemy
│   │   ├── schemas/             # Pydantic
│   │   ├── api/                 # FastAPI routers
│   │   │   ├── auth.py
│   │   │   ├── embed.py
│   │   │   ├── admin/
│   │   │   └── me.py
│   │   ├── views/               # Jinja2 routes (HTML)
│   │   ├── templates/           # Jinja2 *.html
│   │   ├── static/
│   │   │   ├── css/             # tailwind output
│   │   │   ├── js/
│   │   │   └── img/
│   │   └── tests/
│   └── tailwind.config.js
└── docs/
    └── architecture.md
```

---

## 10. Docker Compose (Sketch)

```yaml
services:
  app:
    build: ./app
    expose: ["7788"]
    env_file: .env
    depends_on: [postgres, redis]
    restart: unless-stopped

  nginx:
    build: ./nginx
    ports: ["7789:443", "7780:80"]
    depends_on: [app]
    restart: unless-stopped
    volumes:
      - ./nginx/certs:/etc/nginx/certs:ro

  postgres:
    image: postgres:16-alpine
    volumes: [pgdata:/var/lib/postgresql/data]
    env_file: .env
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    restart: unless-stopped

volumes:
  pgdata:
```

**Port mapping**:
- App internal: `7788` (FastAPI uvicorn)
- Public HTTPS: `7789`
- Public HTTP redirect: `7780`

---

## 11. Environment Variables

```env
# App
APP_ENV=production
APP_SECRET_KEY=<random 64 char>
APP_BASE_URL=https://portal.example.com:7789

# DB
POSTGRES_HOST=postgres
POSTGRES_DB=roc_portal
POSTGRES_USER=roc
POSTGRES_PASSWORD=<strong>

# Redis
REDIS_URL=redis://redis:6379/0

# Azure / Power BI
AZURE_TENANT_ID=
AZURE_CLIENT_ID=
AZURE_CLIENT_SECRET=
PBI_DEFAULT_WORKSPACE_ID=

# Auth
JWT_ALGORITHM=HS256
ACCESS_TOKEN_TTL_MIN=15
REFRESH_TOKEN_TTL_DAYS=7

# SMTP (forgot password)
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=no-reply@example.com
```

---

## 12. Implementation Roadmap

| Phase | Scope | Estimated |
|---|---|---|
| **Phase 0** | Repo scaffold, Docker, Tailwind pipeline, base layout | 2 hari |
| **Phase 1** | Auth (login, JWT, password hash, lockout) | 3 hari |
| **Phase 2** | RBAC + user/role/permission CRUD | 3 hari |
| **Phase 3** | Power BI Service Principal integration + embed flow | 3 hari |
| **Phase 4** | Report & menu management UI | 2 hari |
| **Phase 5** | Site Configuration + theming dinamis | 2 hari |
| **Phase 6** | Audit log + admin dashboard | 2 hari |
| **Phase 7** | 2FA + forgot password + email | 2 hari |
| **Phase 8** | Hardening (CSP, rate limit, watermark) + tests | 3 hari |
| **Phase 9** | Documentation, deployment guide, QA | 2 hari |
| **Total** |  | **~24 hari kerja** |

---

## 13. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Service Principal credential bocor | Tinggi | Docker secret, Azure Key Vault di prod, rotation 90 hari |
| Embed token di-extract via DevTools | Tinggi | Token short-lived, tidak di localStorage, audit log + anomaly detection |
| User screenshot data | Sedang | Watermark dinamis, audit log, T&C |
| RLS misconfiguration | Sedang | Test connection feature, staging env wajib |
| Tenant Power BI policy berubah | Sedang | Doc dependency Azure, monitor MS roadmap |
| DB compromise | Tinggi | Encryption at rest, backup harian, password hashing kuat |

---

## 14. Acceptance Criteria

- [ ] User dapat login dengan email/password.
- [ ] Inspect Element pada halaman report TIDAK menampilkan embed URL atau token Power BI dalam source HTML awal.
- [ ] Token PBI hanya muncul setelah autentikasi via XHR ke endpoint backend.
- [ ] Admin dapat membuat role baru, assign permission, assign ke user, tanpa restart aplikasi.
- [ ] Admin dapat menambah report baru via UI dan langsung muncul di menu user yang berhak.
- [ ] Site Configuration (logo, nama, warna) dapat diubah admin dan terlihat real-time.
- [ ] Audit log mencatat semua login + embed request.
- [ ] Aplikasi berjalan via `docker compose up` di port 7789 (HTTPS).
- [ ] Lighthouse score ≥ 90 untuk Performance & Accessibility.
- [ ] Pen-test internal: tidak ada finding High/Critical.

---

## 15. Resolved Decisions (dari diskusi 2026-04-28)

| # | Topik | Keputusan |
|---|---|---|
| 1 | Akses jaringan | **Internet publik** → wajib TLS valid (Let's Encrypt), WAF/Cloudflare di depan, fail2ban, geo-block opsional |
| 2 | Authentication | **Email / username / ID + password** (no SSO di v1; SSO masuk roadmap v2) |
| 3 | Skala report | **~50 report**, growth wajar; tidak perlu sharding, single Postgres cukup |
| 4 | Tenancy | **Multi-tenant** → semua tabel scoped by `tenant_id`, super-admin lintas tenant, admin per-tenant |
| 5 | Bahasa | **Bilingual: Indonesia & English** (i18n via `babel` + JSON catalog, switcher di header, default ID) |
| 6 | Export | **PDF & PPTX** via Power BI Export API (`exportToFile`), async polling, hasil disimpan sementara di Redis/temp dengan TTL 15 menit, audit log |

### 15.1. Multi-Tenant Schema Adjustments

Tambahkan tabel `tenants` dan kolom `tenant_id` di hampir semua tabel data:

```sql
tenants(id, slug UNIQUE, name, domain UNIQUE NULL, logo_url, primary_color, is_active, created_at)
-- Tambah tenant_id FK ke: users, roles, reports, menu_items, site_config, audit_logs
-- site_config jadi (tenant_id, key) PK — config per-tenant
-- Resolve tenant via subdomain (acme.portal.example.com) atau path (/t/acme) — pilihan deploy
```

Role baru: **`super_admin`** (cross-tenant), **`tenant_admin`** (scope satu tenant).

Middleware `TenantResolver` set `request.state.tenant` dari subdomain/path; semua query auto-filter `WHERE tenant_id = current_tenant`.

### 15.2. i18n Implementation

- Library: `babel` + `fastapi-babel` atau custom (lightweight, JSON-based)
- Locale files: `app/src/locales/id.json`, `app/src/locales/en.json`
- Detection order: cookie `lang` → Accept-Language header → tenant default → `id`
- UI: language switcher di header (🇮🇩 ID / 🇬🇧 EN)
- Date/number format mengikuti locale (Babel)

### 15.3. Export to PDF / PPTX

- Endpoint: `POST /api/embed/{slug}/export` body: `{ format: "PDF" | "PPTX", pages?: [...] }`
- Flow:
  1. Validate permission (`report.export` baru, terpisah dari `report.view`)
  2. Call PBI `POST /reports/{id}/ExportTo` → dapat `exportId`
  3. Background task (FastAPI BackgroundTasks atau Celery di Phase ≥ 8) polling status tiap 5s
  4. Saat `Succeeded`, download file, simpan di `/tmp/exports/{uuid}.{ext}` dengan TTL 15 menit (cron clean)
  5. Return ke client: `{ download_url: "/api/exports/{uuid}", expires_at }`
  6. Audit log: user X export report Y format Z
- Permission baru: `report.export` (toggle di site config `feature.allow_export`)
- Rate limit: 5 export / jam / user

---

## 16. Updated Roadmap (Revised)

| Phase | Scope | Estimated |
|---|---|---|
| **Phase 0** | Repo scaffold, Docker, Tailwind, base layout, i18n skeleton | 2 hari |
| **Phase 1** | Tenants + Auth (login, JWT, lockout, tenant resolver) | 4 hari |
| **Phase 2** | RBAC + user/role/permission CRUD (tenant-scoped) | 3 hari |
| **Phase 3** | Power BI Service Principal + embed flow + watermark | 3 hari |
| **Phase 4** | Report & menu management (per-tenant) | 2 hari |
| **Phase 5** | Site Configuration (per-tenant) + theming dinamis | 2 hari |
| **Phase 6** | Audit log + admin dashboard | 2 hari |
| **Phase 7** | 2FA + forgot password + email | 2 hari |
| **Phase 8** | Export PDF/PPTX (PBI exportToFile) | 2 hari |
| **Phase 9** | i18n full coverage (semua string ID/EN) | 2 hari |
| **Phase 10** | Hardening (CSP, rate limit, fail2ban, WAF setup) + tests | 3 hari |
| **Phase 11** | Documentation, deploy guide (public internet), QA | 2 hari |
| **Total** |  | **~29 hari kerja** |

---

*End of PRD v1.1.0 — updated 2026-04-28*
