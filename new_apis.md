# Nuvo Hosting — Mobile API Reference

> **Base URL:** `https://<your-domain>/api/master`
> **Auth:** None required for all 3 endpoints below

---

## 1. Crew Gallery

Get all active crew member images to display in the **"Our Crew"** section of the app.

**Endpoint**
```
GET /api/master/crew/public/
```

| Field | Value |
|---|---|
| Method | `GET` |
| Auth | ❌ Not required |
| Request Body | None |

**Success Response `200`**
```json
{
  "success": true,
  "message": "Crew members fetched",
  "data": [
    {
      "id": "e3f1a2b4-...",
      "name": "Priya Sharma",
      "image": "https://nuvohosting.s3.ap-south-1.amazonaws.com/staff/crew/e3f1a2b4.jpg",
      "is_active": true,
      "created_at": "2025-05-18 10:30:00",
      "updated_at": "2025-05-18 10:30:00"
    },
    {
      "id": "b7c9d1e2-...",
      "name": "Monica Dsouza",
      "image": "https://nuvohosting.s3.ap-south-1.amazonaws.com/staff/crew/b7c9d1e2.jpg",
      "is_active": true,
      "created_at": "2025-05-18 11:00:00",
      "updated_at": "2025-05-18 11:00:00"
    }
  ]
}
```

**Notes**
- Only returns members where `is_active = true`
- Results sorted alphabetically by name
- `image` is a direct public S3 URL — use it directly in the `<Image />` component
- No pagination — admin controls the list size from the admin panel

---

## 2. Payment Config

Fetch all pricing data needed to calculate event cost on the booking screen.

**Endpoint**
```
GET /api/master/payment/config/
```

| Field | Value |
|---|---|
| Method | `GET` |
| Auth | ❌ Not required |
| Request Body | None |

**Success Response `200`**
```json
{
  "success": true,
  "message": "Payment config fetched",
  "data": {
    "advancePercentage": 30,
    "staff_pricing": {
      "BRONZE":   15000,
      "SILVER":   30000,
      "GOLD":     45000,
      "PLATINUM": 65000
    },
    "default_hours_per_day": 5.0,
    "overtime_rate_per_hour": 3000.0
  }
}
```

**Notes**
- `staff_pricing` values are **per person per day** in INR
- **Diamond** tier is not included — pricing is negotiated directly and added manually to the event
- All values are editable by the admin from the Master Data → Payment Terms panel

**Frontend Calculation Logic**
```js
// Base cost
const base = staff_pricing[tier] × num_staff × num_days

// Overtime (charged only if event exceeds default hours)
const extraHours = Math.max(0, actual_hours - default_hours_per_day)
const overtime   = extraHours × overtime_rate_per_hour × num_staff

// Total event cost
const total = base + overtime

// Advance due at booking
const advance = total × (advancePercentage / 100)
const balance = total - advance
```

**Example:** 5 Bronze staff, 1 day, 7 hours
```
base      = 15,000 × 5 × 1      = ₹75,000
overtime  = (7 - 5) × 3,000 × 5 = ₹30,000
total     =                        ₹1,05,000
advance   = 1,05,000 × 30%      = ₹31,500
balance   =                        ₹73,500
```

---

## 3. Validate & Apply Coupon

Validate a coupon code entered by the client on the checkout screen and get its discount details.

**Endpoint**
```
POST /api/master/coupons/validate/
Content-Type: application/json
```

| Field | Value |
|---|---|
| Method | `POST` |
| Auth | ❌ Not required |
| Content-Type | `application/json` |

**Request Body**
```json
{
  "code": "SAVE20"
}
```

**Success Response `200`**
```json
{
  "success": true,
  "message": "Coupon is valid",
  "data": {
    "code": "SAVE20",
    "description": "20% off for new clients",
    "discount_type": "PERCENTAGE",
    "discount_value": 20,
    "usage_limit": 2,
    "is_active": true
  }
}
```

**Error Responses**

| Message | Reason |
|---|---|
| `"Invalid coupon code"` | Code does not exist |
| `"This coupon is no longer active"` | Admin has disabled the coupon |
| `"This coupon has reached its usage limit"` | Used as many times as allowed |
| `"This coupon has expired"` | Past the expiry date |

All error responses follow the shape:
```json
{ "success": false, "message": "<reason>" }
```

**Frontend Discount Calculation**
```js
if (coupon.discount_type === 'PERCENTAGE') {
  discount = (coupon.discount_value / 100) * total_amount
  // e.g. 20% of ₹75,000 = ₹15,000 off → final = ₹60,000
} else {
  // FLAT
  discount = coupon.discount_value
  // e.g. ₹5,000 flat off → final = ₹75,000 - ₹5,000 = ₹70,000
}

// Safety — final amount should never go below 0
final_amount = Math.max(0, total_amount - discount)
```

**Remove Coupon**
No API call needed — just clear the coupon from state and recalculate the total.

```js
setCoupon(null)   // clear applied coupon
// total reverts back to original amount
```

**Important:** `used_count` is **not incremented** on validate. It must be incremented only when the event booking is **confirmed**. This will be handled in the event booking API — coordinate with the backend team.

---

## 4. Event Booking Payment (PhonePe v2)

Pay for an event booking (advance or balance). PhonePe v2 OAuth-based checkout.

### 4a. Initiate Payment

```
POST /api/events/<event_id>/payment/initiate/
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

**Request Body**
```json
{
  "amount":       31500.00,
  "redirect_url": "nuvoapp://payment/result"
}
```

| Field | Required | Notes |
|---|---|---|
| `amount` | ✅ | Amount in INR (e.g. `31500.00` for ₹31,500). Usually the advance amount. |
| `redirect_url` | ✅ | Deep link or URL where PhonePe redirects the user after checkout. |

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

**Flow:**
1. Open `redirect_url` in an in-app browser / WebView
2. User completes payment on PhonePe
3. PhonePe redirects to your `redirect_url` deep link
4. On return, call `GET /api/events/<id>/` to check updated `payment.payment_status`

### 4b. Payment Callback

```
GET /api/events/payment/callback/?merchantOrderId=EVT-ABCD1234-XY123456
```

PhonePe redirects here after checkout (server-side). You don't need to call this yourself — PhonePe hits it automatically. It updates the event payment status.

**Response**
```json
{
  "success": true,
  "data": {
    "state":          "COMPLETED",
    "event_id":       "...",
    "payment_status": "paid_fully",
    "paid_amount":    31500.0
  }
}
```

`payment_status` values: `"advance"` | `"paid_fully"`

---

## 5. Subscription Plans & Payment (PhonePe v2)

### 5a. List Plans

```
GET /api/subscriptions/plans/
```

No auth required.

**Response**
```json
{
  "success": true,
  "data": [
    {
      "id":              "uuid",
      "name":            "GOLD",
      "monthlyPrice":    999.0,
      "yearlyPrice":     9999.0,
      "prioritySupport": false,
      "isFree":          false
    },
    {
      "name": "PLATINUM",
      "monthlyPrice": 1999.0,
      "yearlyPrice":  19999.0,
      "prioritySupport": true,
      "isFree": false
    },
    {
      "name": "DIAMOND",
      "monthlyPrice": 2999.0,
      "yearlyPrice":  29999.0,
      "prioritySupport": true,
      "isFree": false
    }
  ]
}
```

### 5b. Initiate Subscription Payment

```
POST /api/subscriptions/initiate/
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

**Request Body**
```json
{
  "plan":          "GOLD",
  "billing_cycle": "monthly",
  "redirect_url":  "nuvoapp://subscription/result"
}
```

| Field | Required | Notes |
|---|---|---|
| `plan` | ✅ | `GOLD` \| `PLATINUM` \| `DIAMOND` |
| `billing_cycle` | ✅ | `monthly` \| `yearly` |
| `redirect_url` | ✅ | Deep link PhonePe redirects to after checkout |

**Success Response `200`**
```json
{
  "success": true,
  "data": {
    "redirect_url":      "https://mercury.phonepe.com/transact/pay?token=...",
    "merchant_order_id": "SUB-XXXXXXXXXXXXXXXX"
  }
}
```

**Flow:**
1. Call `GET /api/subscriptions/plans/` to display prices
2. User picks plan + billing cycle → call `POST /api/subscriptions/initiate/`
3. Open `redirect_url` in WebView
4. PhonePe redirects to your `redirect_url` deep link on finish
5. Call `GET /api/subscriptions/my/` to confirm the plan is now active

### 5c. My Subscription

```
GET /api/subscriptions/my/
Authorization: Bearer <jwt_token>
```

**Response**
```json
{
  "success": true,
  "data": {
    "current_plan":  "GOLD",
    "is_active":     true,
    "plan":          "GOLD",
    "billing_cycle": "monthly",
    "amount":        999.0,
    "start_date":    "2026-06-13T10:30:00",
    "end_date":      "2026-07-13T10:30:00"
  }
}
```

| Field | Notes |
|---|---|
| `current_plan` | The plan stored on the client profile (`SILVER` if no paid plan) |
| `is_active` | `true` if the latest subscription's `end_date` is in the future |
| `end_date` | Monthly = 30 days, Yearly = 365 days from payment |

If the user has never subscribed:
```json
{
  "success": true,
  "data": {
    "current_plan": "SILVER",
    "is_active":    false,
    "plan":         null,
    "billing_cycle": null,
    "amount":       null,
    "start_date":   null,
    "end_date":     null
  }
}
```

### 5d. Webhook (do not call — PhonePe only)

```
POST /api/subscriptions/webhook/
```

This endpoint is called by PhonePe's servers, not by the app. Configure it in your PhonePe merchant dashboard → Webhook URL. It is the reliable path — updates subscription even if the app was backgrounded during checkout.
