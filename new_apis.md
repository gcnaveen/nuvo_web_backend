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
