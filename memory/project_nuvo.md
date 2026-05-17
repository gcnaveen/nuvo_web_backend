---
name: project-nuvo
description: Nuvo hosting project — stack, structure, and active feature work
metadata:
  type: project
---

Multi-platform event hosting product: React Native mobile app, React JS admin panel, Python Django (MongoEngine + MongoDB) backend, S3 for image storage.

Backend lives at `nuvo_web_backend/`, frontend (admin) at `nuvo_web_frountend/`.

Key apps: `apps/master/` (themes, uniforms, crew, subscriptions, payment terms), `apps/accounts/`, `apps/users/`, `apps/events/`.

Pattern: all views use `api_response()` helper, S3 uploads via `_s3_upload()`, auth via `@require_auth` + `@require_role` decorators.

**Why:** Client requested several admin-configurable features.

**How to apply:** Follow the existing view/model/url pattern in `apps/master/` for any new master data features.

## Features completed
- **Feature 1 (Crew Gallery)** — `CrewMember` model (`crew_members` collection), CRUD views + public list endpoint, URLs under `/master/crew/`, admin tab "Crew Gallery" in `MasterData.jsx`, API calls in `masterApi.js`.

## Features pending
- **Feature 2** — Extend `PaymentTerms` with staff pricing per tier (Bronze 15k, Silver 30k, Gold 45k, Platinum 65k — Diamond excluded), `default_hours_per_day` (5hrs), `overtime_rate_per_hour` (3k/hr). All editable by admin in Payment Terms tab.
- **Feature 3** — `Coupon` model: code, discount type/value, usage_limit, used_count, is_active, expiry_date. New "Coupons" tab in MasterData.
