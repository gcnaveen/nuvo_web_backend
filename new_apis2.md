# Nuvo Hosting — Phase 2 API Reference

> **Base URL:** `https://<your-domain>/api`
> This document covers APIs added in Phase 2: the Luxury/Premium crew package system, updated event booking, and invoice generation.
> For Phase 1 APIs (Crew Gallery, Payment Config, Coupon Validate, Subscription), see `new_apis.md`.

---

# MOBILE APP APIs

APIs consumed by the **client-facing mobile app**.

---

## M1. Get Crew Package Pricing

Fetch Luxury and Premium pricing before showing the booking screen. Use these values to calculate and display the estimated total to the client.

```
GET /api/master/packages/
```

| Field        | Value           |
| ------------ | --------------- |
| Auth         | ❌ Not required |
| Request Body | None            |

**Response `200`**

```json
{
  "success": true,
  "message": "Crew packages fetched",
  "data": [
    {
      "id":               "uuid",
      "type":             "LUXURY",
      "price_per_person": 20000.0,
      "standard_hours":   8,
      "extra_hour_rate":  2500.0,
      "last_updated":     "2026-07-01T10:30:00"
    },
    {
      "id":               "uuid",
      "type":             "PREMIUM",
      "price_per_person": 10000.0,
      "standard_hours":   8,
      "extra_hour_rate":  1250.0,
      "last_updated":     "2026-07-01T10:30:00"
    }
  ]
}
```

| Field                | Notes                                                                                 |
| -------------------- | ------------------------------------------------------------------------------------- |
| `price_per_person` | Base price per person for`standard_hours` (INR)                                     |
| `standard_hours`   | Hours included in the base price (default: 8)                                         |
| `extra_hour_rate`  | Per extra hour per person — auto-calculated as`price_per_person ÷ standard_hours` |

**Client-Side Pricing Calculation**

```js
function calcTotal(packages, packageType, luxuryCount, premiumCount, workingHours) {
  const lux  = packages.find(p => p.type === 'LUXURY');
  const pre  = packages.find(p => p.type === 'PREMIUM');
  const extraH = Math.max(0, workingHours - 8);
  let total = 0;

  if ((packageType === 'LUXURY' || packageType === 'BOTH') && lux) {
    total += (lux.price_per_person * luxuryCount) + (extraH * lux.extra_hour_rate * luxuryCount);
  }
  if ((packageType === 'PREMIUM' || packageType === 'BOTH') && pre) {
    total += (pre.price_per_person * premiumCount) + (extraH * pre.extra_hour_rate * premiumCount);
  }
  return total;
}
```

**Worked Examples** (default prices: Luxury ₹20,000 / Premium ₹10,000, 8 standard hours)

| Scenario        | Input                        | Total      |
| --------------- | ---------------------------- | ---------- |
| Luxury only     | 5 Luxury, 8 hrs              | ₹1,00,000 |
| Premium only    | 5 Premium, 8 hrs             | ₹50,000   |
| Both            | 5 Luxury + 5 Premium, 8 hrs  | ₹1,50,000 |
| Both + overtime | 5 Luxury + 5 Premium, 10 hrs | ₹1,87,500 |

---

## M2. Create Event Booking

Client submits a new event booking from the app.

```
POST /api/events/create/
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

> **Breaking change from Phase 1:** `crew_count`, `package_id`, and `total_amount` are removed. Use the new package fields below.

**Request Body**

```json
{
  "event_name":           "Sharma Wedding",
  "event_type":           "Wedding",
  "city":                 "Mumbai",
  "state":                "Maharashtra",
  "client_id":            "<client-profile-uuid>",
  "event_start_datetime": "2026-08-15T10:00",
  "event_end_datetime":   "2026-08-15T20:00",
  "no_of_days":           1,
  "working_hours":        10,

  "package_type":         "BOTH",
  "luxury_crew_count":    5,
  "premium_crew_count":   5,

  "payment_method":       "ONLINE",
  "advance_type":         "HALF",

  "venue": {
    "venue_name":         "Grand Hyatt Mumbai",
    "formatted_address":  "Off Western Express Hwy, Santacruz East, Mumbai",
    "latitude":           19.0896,
    "longitude":          72.8656,
    "place_id":           "ChIJ...",
    "google_maps_url":    "https://maps.google.com/?q=19.0896,72.8656"
  },

  "theme_id":   "theme-uuid-optional",
  "uniform_id": "uniform-uuid-optional",

  "payment": {
    "gst_amount": 0,
    "tax_amount": 0
  }
}
```

**New Package Fields**

| Field                  | Type   | Required | Values                                                                          |
| ---------------------- | ------ | -------- | ------------------------------------------------------------------------------- |
| `package_type`       | string | ❌       | `LUXURY` \| `PREMIUM` \| `BOTH`                                           |
| `luxury_crew_count`  | int    | ❌       | Number of Luxury crew (needed when`package_type` is `LUXURY` or `BOTH`)   |
| `premium_crew_count` | int    | ❌       | Number of Premium crew (needed when`package_type` is `PREMIUM` or `BOTH`) |
| `payment_method`     | string | ❌       | `ONLINE` (default) \| `CASH`                                                |
| `advance_type`       | string | ❌       | `FULL` (default) \| `HALF` — see payment rules below                       |

**Removed Fields — do not send**

| Removed          | Replaced by                                     |
| ---------------- | ----------------------------------------------- |
| `crew_count`   | `luxury_crew_count` / `premium_crew_count`  |
| `package_id`   | `package_type`                                |
| `total_amount` | Auto-calculated by backend from package pricing |

**Payment Collection Rules**

| Days to event | Allowed`advance_type` | Backend behaviour                                                                          |
| ------------- | ----------------------- | ------------------------------------------------------------------------------------------ |
| ≤ 7 days     | `FULL` only           | `HALF` is silently overridden to `FULL`                                                |
| 8 – 12 days  | `FULL` only           | —                                                                                         |
| > 12 days     | `FULL` or `HALF`    | If`HALF`: balance due date = event date − 7 days. Reminder email is sent automatically. |

**Success Response `201`**

```json
{
  "success": true,
  "message": "Event created successfully",
  "data": {
    "id": "event-uuid",
    "event_name": "Sharma Wedding",
    "package_type": "BOTH",
    "luxury_crew_count": 5,
    "premium_crew_count": 5,
    "payment": {
      "total_amount":     187500.0,
      "paid_amount":      0,
      "gst_amount":       0,
      "payment_method":   "ONLINE",
      "advance_type":     "HALF",
      "balance_due_date": "2026-08-08T10:00:00",
      "payment_status":   "unpaid",
      "invoice_url":      null
    }
  }
}
```

---

## M3. Initiate Event Payment (PhonePe)

Start a PhonePe checkout for an event (advance or balance payment).

```
POST /api/events/<event_id>/payment/initiate/
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

**Request Body**

```json
{
  "amount":       93750.0,
  "redirect_url": "nuvoapp://payment/result"
}
```

| Field            | Notes                                                                                                   |
| ---------------- | ------------------------------------------------------------------------------------------------------- |
| `amount`       | Amount to charge now (INR). Pass`total_amount ÷ 2` for HALF advance, full `total_amount` for FULL. |
| `redirect_url` | Deep link PhonePe redirects to after checkout completes                                                 |

**Success Response `200`**

```json
{
  "success": true,
  "message": "Payment initiated",
  "data": {
    "redirect_url":      "https://mercury.phonepe.com/transact/pay?token=...",
    "merchant_order_id": "EVT-ABCD1234-XY123456"
  }
}
```

**Payment Flow**

```
1. Call POST /api/events/<id>/payment/initiate/
2. Open data.redirect_url in an in-app WebView
3. User completes PhonePe checkout
4. PhonePe redirects to your redirect_url deep link
5. Call GET /api/events/<id>/ to read updated payment.payment_status
6. Call GET /api/events/<id>/invoice/ to get the PDF invoice
```

**`payment_status` values after payment**

| Value          | Meaning                               |
| -------------- | ------------------------------------- |
| `advance`    | 50% paid — balance still outstanding |
| `paid_fully` | 100% paid — event fully settled      |

---

## M4. Get Event Invoice

Fetch the PDF invoice for a completed/paid event. Auto-generates the invoice if it hasn't been created yet (e.g. first time fetching after a cash event).

```
GET /api/events/<event_id>/invoice/
Authorization: Bearer <jwt_token>
```

**Success Response `200`**

```json
{
  "success": true,
  "message": "Invoice fetched",
  "data": {
    "invoice_url":    "https://nuvohosting.s3.ap-south-1.amazonaws.com/invoices/NVH-202608-A1B2C3.pdf",
    "invoice_number": "NVH-202608-A1B2C3"
  }
}
```

| Field              | Notes                                                         |
| ------------------ | ------------------------------------------------------------- |
| `invoice_url`    | Direct public S3 URL — open in browser or share directly     |
| `invoice_number` | Format:`NVH-{YYYYMM}-{first 6 chars of event_id uppercase}` |

---

## M5. My Events (Client)

Fetch all events belonging to the logged-in client.

```
GET /api/events/get-my-events/
Authorization: Bearer <jwt_token>
```

Returns a list of the client's events with payment and package details.

---

---

# ADMIN PANEL APIs

APIs consumed by the **web-based admin panel**. All require `ADMIN` role JWT.

---

## A1. Set Crew Package Pricing

Admin sets the per-person price and standard hours for Luxury and Premium packages. This is done from the **Master Data → Crew Packages** tab in the admin panel.

```
PUT /api/master/packages/<package_type>/
Authorization: Bearer <admin_jwt_token>
Content-Type: application/json
```

`<package_type>` must be `LUXURY` or `PREMIUM` (case-insensitive).

**Request Body**

```json
{
  "price_per_person": 20000,
  "standard_hours":   8
}
```

| Field                | Type  | Required | Notes                                                   |
| -------------------- | ----- | -------- | ------------------------------------------------------- |
| `price_per_person` | float | ✅       | Per-person price in INR for the standard working hours  |
| `standard_hours`   | int   | ✅       | Number of hours included in the base price (default: 8) |

The backend auto-calculates `extra_hour_rate = price_per_person ÷ standard_hours`.

**Success Response `200`**

```json
{
  "success": true,
  "message": "LUXURY package updated",
  "data": {
    "id":               "uuid",
    "type":             "LUXURY",
    "price_per_person": 20000.0,
    "standard_hours":   8,
    "extra_hour_rate":  2500.0,
    "last_updated":     "2026-07-02T09:00:00"
  }
}
```

**Error Responses**

| HTTP    | Message                                                 | Reason                 |
| ------- | ------------------------------------------------------- | ---------------------- |
| `400` | `"package_type must be one of ['LUXURY', 'PREMIUM']"` | Invalid URL parameter  |
| `401` | Unauthorized                                            | Missing or invalid JWT |
| `403` | Forbidden                                               | Non-admin user         |

**Note:** Creates the document if it doesn't exist yet (upsert). Safe to call multiple times.

---

## A2. Create Event (Admin on behalf of client)

Same endpoint as M2 (`POST /api/events/create/`) but called by the admin when a client books through the admin panel directly.

```
POST /api/events/create/
Authorization: Bearer <admin_jwt_token>
Content-Type: application/json
```

Request body and rules are identical to **M2** above. The admin selects the client from a dropdown — the `client_id` in the body is the selected client's profile UUID.

---

## A3. Update Event

```
PUT /api/events/<event_id>/update/
Authorization: Bearer <admin_jwt_token>
Content-Type: application/json
```

Supports updating all fields including the new package fields:

```json
{
  "package_type":        "LUXURY",
  "luxury_crew_count":   6,
  "premium_crew_count":  0,
  "working_hours":       9
}
```

When `package_type`, `luxury_crew_count`, `premium_crew_count`, or `working_hours` is updated, the backend **recalculates `total_amount` automatically**.

---

## A4. Get Event Invoice (Admin)

Same endpoint as M4. Admin can use it to fetch or regenerate an invoice for any event.

```
GET /api/events/<event_id>/invoice/
Authorization: Bearer <admin_jwt_token>
```

---

## A5. List Crew Packages (Admin Panel)

Same as M1 — used by the admin panel's event creation form to display pricing and show live cost preview while filling in crew counts.

```
GET /api/master/packages/
```

No auth required. See **M1** for full response shape.

---

---

# QUICK REFERENCE

| Endpoint                               | Method | Auth              | Consumer                     |
| -------------------------------------- | ------ | ----------------- | ---------------------------- |
| `/api/master/packages/`              | GET    | ❌ None           | Mobile + Admin               |
| `/api/master/packages/<type>/`       | PUT    | ✅ Admin          | Admin only                   |
| `/api/events/create/`                | POST   | ✅ Client / Admin | Mobile + Admin               |
| `/api/events/<id>/`                  | GET    | ✅ Any            | Mobile + Admin               |
| `/api/events/<id>/update/`           | PUT    | ✅ Admin          | Admin only                   |
| `/api/events/<id>/payment/initiate/` | POST   | ✅ Client         | Mobile only                  |
| `/api/events/<id>/invoice/`          | GET    | ✅ Any            | Mobile + Admin               |
| `/api/events/get-my-events/`         | GET    | ✅ Client         | Mobile only                  |
| `/api/events/payment/callback/`      | GET    | ❌ PhonePe        | Internal (PhonePe → server) |
| `/api/events/payment/webhook/`       | POST   | ❌ PhonePe        | Internal (PhonePe → server) |
