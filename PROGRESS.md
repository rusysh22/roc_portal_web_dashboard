# PROGRESS LOG — ROC Portal Power BI

---

## [2026-04-29] Phase 5 — Site Config Theming + Shared Context COMPLETE

### Done
- [x] **`core/site_config.py`** — `get_site_config(tenant_id, db, redis)` dengan Redis cache 5 menit; `_generate_palette()` menghasilkan 7 shade HSV dari primary hex; `invalidate_cache()` dipanggil saat config di-update
- [x] **`views/_context.py`** — `build_base_context()` (semua halaman authenticated) + `build_auth_context()` (login/forgot/reset) — eliminasi duplikasi di 8 view files
- [x] **Refactor semua view handlers** ke `build_base_context` / `build_auth_context`: me, reports, dashboard, admin/users, admin/roles, admin/reports, admin/config, auth
- [x] **`base.html`** — inject `<style>:root{...}</style>` dengan 7 primary CSS vars + secondary + brand-primary + brand-secondary; dark mode flash prevention (inline script sebelum Alpine)
- [x] **Favicon** — diambil dari `site.favicon_url` config
- [x] **`layout.html`** — logo dari `site_config['site.logo_url']` > `tenant.logo_url` > initials; dark mode toggle button (moon/sun) di topbar; announcement banner (`site.announcement`) dismissable
- [x] **Dark mode toggle** — `toggleDark()` di `portalLayout()`, persist ke `localStorage`, init dari localStorage/OS preference sebelum Alpine
- [x] **Cache invalidation** — `api/admin/config.py` memanggil `invalidate_cache()` setelah setiap PUT, sehingga perubahan langsung efektif di halaman berikutnya
- [x] **i18n** — tambah `common.dark_mode`, `common.light_mode`

### Verified (live test)
- CSS vars muncul di `<style>` block setiap halaman ✓
- Ubah `site.primary_color` → warna langsung berubah di halaman berikutnya ✓
- `site.announcement` → banner muncul di topbar (dismissable) ✓
- Login page juga mendapat CSS vars (9 var ditemukan) ✓
- Dark mode toggle berfungsi + persist di localStorage ✓
- Semua 8 endpoint halaman → 200 ✓

### Next Up — Phase 6: Audit Log Viewer + Admin Dashboard
1. `api/admin/audit.py` — `GET /api/admin/audit` (filter by user/action/date, paging)
2. `views/admin/audit.py` + `templates/admin/audit.html` — tabel log dengan filter
3. `templates/admin/dashboard.html` — summary stats (total user, report, login today, dll)
4. `views/admin/dashboard.py` — aggregated stats dari DB

---

## [2026-04-29] Phase 4 — Sidebar Nav Dinamis + Site Config + Export API COMPLETE

### Phase 3 Fixes
- [x] Bug `_embed()` non-async: `SyntaxError await` → `async _embed()` di `viewer/report.html`
- [x] Bug closure `${slug}` → `${this.slug}` di fetch URL
- [x] `nav_reports: []` hardcoded di semua views → diganti dengan query DB via helper `views/_nav.py`

### Done — Phase 4
- [x] **`views/_nav.py`** — shared `get_nav_reports(tenant_id, user, db)` helper, dipakai semua views
- [x] **Sidebar nav dinamis**: semua 6 view routes (`me`, `reports`, `admin/users`, `admin/roles`, `admin/reports`, `admin/config`) sekarang query DB dan kirim `nav_reports` real ke template
- [x] **`schemas/config.py`** — `SiteConfigRead`, `SiteConfigUpdate` (Pydantic v2)
- [x] **`api/admin/config.py`** — `GET /api/admin/config`, `PUT /api/admin/config/{key}` dengan RBAC `config.edit` + audit log
- [x] **`views/admin/config.py`** — HTML view `/admin/config` dengan RBAC guard
- [x] **`templates/admin/config.html`** — tabbed UI (site/auth/pbi/feature/i18n), per-row save via Alpine.js + fetch, toggle untuk bool, number input untuk int, text untuk string; feedback badge Tersimpan/Gagal per baris
- [x] **Sidebar**: tambah link "Laporan" (admin/reports) dan "Konfigurasi" (admin/config) ke admin section layout.html
- [x] **`api/export.py`** — `POST /api/exports/reports/{slug}` (start job), `GET /api/exports/{job_id}/status`, `GET /api/exports/{job_id}/download` (proxy stream dari PBI); menggunakan FastAPI BackgroundTasks + Redis job state; poll PBI `ExportTo` API setiap 10 detik, max 10 menit
- [x] **`viewer/report.html`** — export button sekarang memanggil `/api/exports/reports/{slug}`, poll status, auto-trigger download saat done
- [x] **i18n**: tambah `report.viewer.export_start/processing/error` + `admin.config.*` di id.json dan en.json
- [x] **`main.py`**: register 4 router baru (export API, admin config API, admin config view)

### Verified (live test)
- `GET /admin/config` → 200 HTML ✓
- `GET /api/admin/config` → 200, 20 config keys ✓
- `PUT /api/admin/config/site.name` → `{"ok":true}` ✓
- nav_reports muncul di sidebar: dashboard, report viewer, me, admin/users ✓
- Link `/admin/config` muncul di sidebar admin section ✓
- App restart clean, semua endpoint 200 ✓

### Note — Export API
Export PDF/PPTX butuh SP (`AZURE_TENANT_ID/CLIENT_ID/CLIENT_SECRET`) untuk live test. Flow sudah complete: BackgroundTask → `ExportTo` → poll → download stream proxy. Untuk `PublicUrl` embed type, export via PBI API tidak disupport (raised 400).

### Next Up — Phase 5: Site Config Theming + Apply to Layout
1. Load `site.*` config dari DB/Redis di setiap request → inject CSS vars ke `base.html`
2. Logo, warna brand, app name dari DB (bukan hardcode)
3. Admin dapat preview perubahan tema real-time
4. Announcement banner dari `site.announcement` config key

---

## [2026-04-29] Phase 2 — RBAC + Admin CRUD COMPLETE

### Done
- [x] **Schemas**: `schemas/user.py` (UserCreate, UserUpdate, UserRead, UserListItem, PasswordChange, PasswordResetByAdmin), `schemas/role.py` (RoleCreate, RoleUpdate, RoleRead, PermissionRead), `schemas/report.py`, `schemas/menu.py`
- [x] **API `GET /api/me`** — profile current user (roles loaded)
- [x] **API `PUT /api/me/password`** — change own password dengan verifikasi current password
- [x] **API `GET /api/me/menu`** — menu items filtered by user permissions
- [x] **API Admin Users** (`/api/admin/users`) — CRUD lengkap: list+search+paging, create, get, update, delete, reset password; semua dengan audit log
- [x] **API Admin Roles** (`/api/admin/roles`) — CRUD: list, create, get, update (dengan permission assignment), delete; guard `is_system`
- [x] **API Admin Permissions** (`/api/admin/permissions`) — read-only list
- [x] **`templates/layout.html`** — app shell: sidebar (nav-item, nav-item-active, admin section, user info), topbar (breadcrumb, lang switcher, logout), flash messages, Alpine.js mobile toggle
- [x] **`templates/admin/users.html`** — SPA-like page: tabel dengan search+paging, modal create/edit (multi-role checklist), modal delete confirm; Alpine.js
- [x] **`templates/admin/roles.html`** — card grid: modal create/edit (permission checklist), modal delete; Alpine.js
- [x] **`templates/me/profile.html`** — info user, form ganti password
- [x] **Views**: `views/admin/users.py`, `views/admin/roles.py`, `views/me.py`
- [x] **CSS**: tambah component classes: `nav-item`, `nav-item-active`, `nav-item-sub`, `badge-*`, `table`, `btn-danger`, `btn-outline`, `form-label`, `form-help`
- [x] **i18n**: tambah key `common.prev/next`, `admin.users.*`, `admin.roles.*`, `me.profile.*` di id.json dan en.json
- [x] `main.py`: register semua 9 router baru

### Verified (live test)
- `GET /api/me` → 200, data user lengkap
- `GET /api/admin/users` → 200, list + pagination
- `POST /api/admin/users` → 201, create user berhasil dengan audit log
- `GET /api/admin/roles` → 200, roles + permissions
- `POST /api/admin/roles` → 201, create role berhasil
- `GET /api/admin/permissions` → 200, daftar semua permission
- `GET /admin/users` → 200 HTML
- `GET /admin/roles` → 200 HTML
- `GET /me` → 200 HTML

### Next Up — Phase 3: Report Viewer + Power BI Embed
1. `core/powerbi.py` — SP auth (MSAL), AAD token cache ke Redis, embed token per user
2. `api/reports.py` — list reports (accessible by user), `GET /api/reports/{slug}/embed` → embed token+url via XHR
3. `views/reports.py` + `templates/viewer/report.html` — Power BI embedded iframe
4. `api/admin/reports.py` — CRUD report config (admin)
5. `templates/admin/reports.html` — report management page

---

> Append-only work log. Newest entry on top. Format setiap entry:
> `## [YYYY-MM-DD HH:MM] Phase X — Topic`
> Lalu bullet apa yang dikerjakan, decision, blocker, next step.

---

## [2026-04-29] Phase 3 — Report Viewer + Power BI Embed COMPLETE

### Done
- [x] **Migration**: tambah kolom `reports.public_url` (nullable) — Alembic `9d20d172cf80`
- [x] **`core/powerbi.py`**: SP auth via MSAL, AAD token cache Redis (`pbi:aad_token:global`), `get_embed_config()` untuk SP embed (workspace/report/RLS), graceful `_is_sp_configured()` check
- [x] **`api/reports.py`**: `GET /api/reports` (list accessible) + `GET /api/reports/{slug}/embed` — dua jalur:
  - `PublicUrl`: return URL langsung (no SP needed)
  - SP embed: call PBI REST API → embed token
  - **URL tidak pernah muncul di server-rendered HTML** (constraint non-negotiable terpenuhi)
- [x] **`api/admin/reports.py`**: CRUD lengkap report config dengan audit log
- [x] **`templates/viewer/report.html`**: embed container dengan powerbi-client.js SDK, toolbar (export placeholder, fullscreen), loading state, error state dengan retry
- [x] **`templates/admin/reports.html`**: tabel admin dengan modal create/edit (PublicUrl + SP fields conditional), preview link, delete confirm
- [x] **`views/reports.py`** + **`views/admin/reports.py`**: Jinja2 HTML routes
- [x] **i18n**: tambah `report.viewer.*`, `admin.reports.*` di id.json + en.json (fixed JSON duplikasi key)
- [x] **main.py**: register 4 router baru (api + view untuk reports + admin/reports)
- [x] Seed report demo: `contoh-pbi` — embed URL dari contoh user (PublicUrl type)

### Verified (live test)
- `GET /api/reports` → 200
- `GET /api/reports/contoh-pbi/embed` → 200, `{"embed_type":"PublicUrl","embed_url":"https://app.powerbi.com/view?r=...","access_token":null}`
- `GET /api/admin/reports` → 200
- `GET /reports/contoh-pbi` → 200 HTML (URL PBI tidak ada di HTML source ✓)
- `GET /admin/reports` → 200 HTML
- SP embed path: implemented, butuh `AZURE_TENANT_ID/CLIENT_ID/CLIENT_SECRET` untuk live test

### Embed type dukung
| Type | Kebutuhan | Use case |
|---|---|---|
| `PublicUrl` | Tidak perlu SP | Publish to web, demo, laporan publik |
| `Report` | Service Principal | Laporan sensitif dengan RBAC & RLS |
| `Dashboard` | Service Principal | Dashboard PBI |

### Next Up — Phase 4: Sidebar Nav Dinamis + Dashboard + Export
1. `GET /api/me/menu` integrate ke nav sidebar (ambil dari DB)
2. `views/dashboard.py` + `templates/dashboard.html` — halaman home setelah login
3. Export API (PDF/PPTX via PBI REST) dengan BackgroundTasks
4. Site config (logo, warna brand) bisa diubah admin via UI

---

## [2026-04-28] Phase 1 — Tenants + Auth COMPLETE

### Done
- [x] SQLAlchemy models: `tenants`, `users`, `roles`, `permissions`, `user_roles`, `role_permissions`, `refresh_tokens`, `reports` (embed by config), `report_role_access`, `menu_items`, `site_configs`, `audit_logs` — 13 tables
- [x] Alembic async env.py + initial migration `8171f449f5a5_initial_schema`
- [x] `core/tenant.py` TenantMiddleware (subdomain/path/X-Tenant-Slug header)
- [x] `core/security.py` (bcrypt cost 12, JWT access/refresh/reset, CSRF, token hash)
- [x] `core/audit.py` (fire-and-forget emit function)
- [x] `core/rbac.py` (require_permission dependency)
- [x] `deps.py` (get_db, get_redis, get_current_user, get_current_tenant)
- [x] `api/auth.py` (login, logout, refresh, forgot, reset — all dengan audit log)
- [x] `views/auth.py` (login, forgot-password, reset-password Jinja2 views)
- [x] `templates/auth/login.html` (bilingual, Alpine.js, Tailwind, password toggle, error handling)
- [x] `templates/auth/forgot_password.html` + `reset_password.html`
- [x] `seed.py` (permissions, default tenant, 19 site_configs, 4 roles, super admin user)
- [x] Report model dengan **embed config by config** (workspace_id, report_id, embed_type, display_config JSONB, rls_config JSONB, export_config JSONB) — admin dapat ubah semua parameter embed via UI
- [x] `main.py` update: TenantMiddleware + auth routers registered

### Verified (live test)
- `GET https://localhost:7789/healthz` → `{"status":"ok"}`
- `GET https://localhost:7789/login` → HTTP 200
- `POST https://localhost:7789/api/auth/login` (admin@example.com / Admin@Portal2026!) → JWT cookie + user data
- `POST https://localhost:7789/api/auth/login` (wrong password) → 401 `invalid_credentials`
- All 13 DB tables created by migration
- Seed: 9 permissions, 1 tenant, 19 site_configs, 4 roles, 1 super admin

### Note on embed "by config"
Report table stores `display_config` JSONB:
```json
{ "height": "600px", "filterPaneEnabled": false, "navContentPaneEnabled": false, "pageView": "fitToWidth" }
```
`rls_config` JSONB untuk Power BI RLS role mapping per portal role.
`export_config` JSONB untuk PDF/PPTX settings.
Semua bisa diedit admin via UI tanpa redeploy (Phase 4).

### Next Up — Phase 2: RBAC + User/Role/Permission CRUD
1. `schemas/user.py`, `schemas/role.py`, `schemas/report.py`, `schemas/menu.py`
2. `api/admin/users.py`, `roles.py`, `permissions.py`
3. Admin HTML pages: user list, user form, role list, role form
4. `api/me.py` (current user profile + accessible menu)
5. Base portal layout (sidebar + topbar) sebagai `templates/layout.html`

---

## [2026-04-28] Phase 0 — Scaffold COMPLETE

### Done
- [x] PRD v1.0 → v1.1.0 (6 open questions resolved)
- [x] CLAUDE.md (project context permanen)
- [x] PROGRESS.md (file ini)
- [x] **Phase 0 scaffold COMPLETE**:
  - `docker-compose.yml` (app, nginx, postgres 16, redis 7, healthchecks, volumes)
  - `app/Dockerfile` (multi-stage: tailwind build + python 3.12 runtime, non-root user, healthcheck)
  - `app/pyproject.toml` (fastapi, sqlalchemy 2, alembic, msal, structlog, babel, pyotp, slowapi)
  - `app/package.json` + `tailwind.config.js` + `postcss.config.js` (Tailwind 3 + forms + typography)
  - `app/src/main.py` (FastAPI app factory, security headers middleware, CSP, healthz, root page)
  - `app/src/config.py` (Pydantic Settings dari env)
  - `app/src/i18n.py` (locale loader + detector, fallback chain: cookie→header→tenant→default)
  - `app/src/locales/{id,en}.json` (initial catalog: app, auth.login, nav, report.viewer, error)
  - `app/src/templates/base.html` + `index.html` (Tailwind, Alpine.js, HTMX via CDN)
  - `app/src/static/src/css/app.css` (Tailwind directives + CSS vars untuk theming dinamis)
  - `app/alembic.ini` + `alembic/env.py` + `script.py.mako` (siap untuk Phase 1 migrations)
  - `nginx/Dockerfile` (self-signed dev cert auto-generated)
  - `nginx/nginx.conf` (HTTP→HTTPS redirect, TLS 1.2/1.3, rate limit zones, security headers, proxy ke app:7788)
  - `nginx/proxy_params.conf` (forwarded headers)
  - `.env.example`, `.gitignore`, `README.md`
- [x] `docker compose config` validation PASS

### Verified
- Docker 28.2.2 + Compose v5.1.0 tersedia di host
- Compose config valid (no syntax error)

### Decisions (added to CLAUDE.md §8)
- Tenant resolution: subdomain primary, path fallback
- Single SP global di v1
- BackgroundTasks (no Celery) di v1

### Open / To Confirm with User
- Domain production untuk subdomain-based tenant
- TLS provisioning di prod (Let's Encrypt vs manual)
- SMTP provider
- Brand default tenant

### Next Up — Phase 1: Tenants + Auth
1. SQLAlchemy models: `tenants`, `users`, `roles`, `permissions`, `user_roles`, `role_permissions`, `refresh_tokens`
2. Alembic initial migration
3. `core/tenant.py` middleware (resolve dari subdomain/path/header X-Tenant-Slug for dev)
4. `core/security.py` (bcrypt hash, JWT issue/verify, CSRF token)
5. `api/auth.py` (login, logout, refresh, forgot, reset)
6. `views/auth.py` + Jinja2 login page (Tailwind, bilingual)
7. `core/audit.py` skeleton
8. Seed script: default tenant + super_admin user

---

### Decisions
- Tenant resolution strategy: **subdomain-based** (acme.portal.example.com) sebagai primary, path-based (`/t/acme`) sebagai fallback dev.
- Single Service Principal global (semua tenant share workspace di Azure tenant yang sama, dipisah per workspace PBI).
- Tidak pakai Celery di v1; FastAPI BackgroundTasks cukup untuk export polling.

### Open / To Confirm with User
- Domain production untuk subdomain tenant resolution
- TLS provisioning: Let's Encrypt auto vs manual?
- SMTP provider pilihan
- Brand default tenant (logo, warna)

### Next Up
1. Buat `docker-compose.yml` (app, postgres, redis, nginx)
2. Buat `app/Dockerfile` dengan Python 3.12 + uv/pip + Tailwind build stage
3. Buat skeleton FastAPI di `app/src/main.py`
4. Tailwind config + base template Jinja2
5. `.env.example` + `.gitignore`
6. Test: `docker compose up` → port 7789 menampilkan halaman placeholder

---

## How to use this log

- Tambah entry baru di **paling atas** setiap sesi/akhir sesi.
- Section per entry: **Done**, **In Progress**, **Decisions**, **Blockers**, **Next Up**.
- Kalau decision arsitektural penting, salin juga ke `CLAUDE.md` section 8.
- Jangan hapus entry lama — log adalah audit trail keputusan.
