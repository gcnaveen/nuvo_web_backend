# Mobile APIS

## 🔑 AUTH APIs (`/api/auth/`)

### Send OTP

`POST /auth/send-otp/`

> **CLIENT:** Email required, account need not exist yet.
> **STAFF / MAKEUP_ARTIST / ADMIN:** Account must exist and not be blocked.

```json
{ "email": "user@gmail.com" }
```

### Verify OTP (Login)

`POST /auth/verify-otp/`

> Returns `403` if account is `PENDING` or blocked.

```json
{ "email": "user@gmail.com", "otp": "123456" }
```

**Response**

```json
{
  "success": true,
  "message": "Login successful",
  "data": {
    "access_token": "...",
    "refresh_token": "...",
    "user": {
      "id": "uuid",
      "email": "user@gmail.com",
      "phone_number": "9999999999",
      "full_name": "Riya Sharma",
      "role": "CLIENT",
      "status": "ACTIVE",
      "is_approved": true,
      "profile_completed": false
    }
  }
}
```

## Get themes [GET] `/master/themes/`

### Responce

```
{
  "success": true,
  "message": "Themes fetched",
  "data": [
    {
      "id": "d1437ab2-acba-49f6-bb0a-c5a5d20f298f",
      "theme_name": "casino night",
      "status": "ACTIVE",
      "description": "casino night",
      "cover_image": "https://nuvohosting.s3.ap-south-1.amazonaws.com/themes/covers/d1437ab2-acba-49f6-bb0a-c5a5d20f298f.jpeg",
      "gallery_images": [
        "https://nuvohosting.s3.ap-south-1.amazonaws.com/themes/gallery/195e22ae-c097-4a22-81e9-3d7cfdb570ce.jpeg",
        "https://nuvohosting.s3.ap-south-1.amazonaws.com/themes/gallery/67b6072f-234f-40e3-b979-03565836615e.jpeg"
      ],
      "created_at": "2026-03-07 15:40:30.427000",
      "updated_at": "2026-03-07 15:40:35.714000"
    },
    {
      "id": "dcd3b2bc-e933-4e58-830a-c199ce82f19f",
      "theme_name": "Wedding",
      "status": "ACTIVE",
      "description": "wedding theme",
      "cover_image": "https://nuvohosting.s3.ap-south-1.amazonaws.com/themes/covers/dcd3b2bc-e933-4e58-830a-c199ce82f19f.jpeg",
      "gallery_images": [
        "https://nuvohosting.s3.ap-south-1.amazonaws.com/themes/gallery/98a45153-1bcd-4a1c-a402-a55ff7e6ef71.webp",
        "https://nuvohosting.s3.ap-south-1.amazonaws.com/themes/gallery/a0551e00-d961-4de0-9f21-bb9d60c86f64.webp"
      ],
      "created_at": "2026-03-07 14:46:27.326000",
      "updated_at": "2026-03-07 14:46:32.469000"
    }
  ]
}
```

## Get/filter uniforms [GET] `/master/uniform/filter/`

### URL Example:

filter with gender : `/master/uniform/filter/?gender=male&is_active=true`
All active data : `/master/uniform/filter/?is_active=true`

## get/filter models/staff [GET] `/users/mobile/modals_list_filter/`

### Filter Reference:

?gender=male
?city=Abu Dhabi
?package=SILVER/GOLD/PLATINUM
?is_active=true,
?page=1
?page_size=15

### Responce

```
{
    "success": true,
    "message": "Staff list fetched",
    "data": {
        "results": [
            {
                "id": "64b1f...",
                "full_name": "Jane Doe",
                "stage_name": "Jane D",
                "gender": "female",
                "city": "Dubai",
                "height": 175.0,
                "package": "GOLD",
                "profile_picture": "https://cdn.example.com/jane_pfp.jpg",
                "gallery_images": [
                    "https://cdn.example.com/jane_1.jpg",
                    "https://cdn.example.com/jane_2.jpg"
                ],
                "status": "active",
                "experience_in_years": 3
            }
        ],
        "pagination": {
            "total": 120,
            "page": 1,
            "page_size": 15,
            "total_pages": 8
        }
    }
}
```

## Create event [POST] /api/events/create/.

### body or payload

### Create Event _(Admin and client)_

`POST /events/create/`

Required: `event_name`, `city`, `state`, `client_id`, `venue.venue_name`, `event_start_datetime`, `event_end_datetime`

```json
{
  "event_name": "Sharma Wedding",
  "event_type": "Wedding",
  "city": "Bangalore",
  "state": "Karnataka",
  "venue": {
    "venue_name": "Royal Orchid Palace",
    "formatted_address": "MG Road, Bangalore, Karnataka 560001",
    "latitude": 12.9716,
    "longitude": 77.5946,
    "place_id": "ChIJ...",
    "google_maps_url": "https://www.google.com/maps/place/?q=place_id:ChIJ..."
  },
  "event_start_datetime": "2026-04-10T18:00:00",
  "event_end_datetime": "2026-04-10T23:00:00",
  "no_of_days": 1,
  "working_hours": 5,
  "crew_count": 5,
  "client_id": "uuid",
  "theme_id": "uuid",
  "uniform_id": "uuid",
  "package_id": "uuid",
  "gst_details": {
    "company_name": "Sharma Enterprises",
    "address": "123 MG Road, Bangalore",
    "gst_number": "29ABCDE1234F1Z5"
  },
  "payment": {
    "total_amount": 125000,
    "gst_amount": 22500,
    "tax_amount": 0
  }
}
```

### responce

```
{
"success": true,
"message": "Event created successfully",
"data": {
"id": "60d5ec49f1b2c8b1f8e4e1a9",
"event_name": "Tech Innovators Summit 2026",
"status": "created"
// ... serialized event data based on serialize_event(event, full=True)
}
}
```

## get my events [GET] `http://127.0.0.1:8000/api/events/get-my-events/`

### Responce

```
{
  "success": true,
  "message": "My events fetched successfully",
  "data": {
    "results": [
      {
        "event_id": "f2babee6-74ab-4dfb-92cb-62cbba2f1a60",
        "event_name": "birthday 1",
        "event_theme_name": "Wedding",
        "order_id": "",
        "payment_details": {
          "total_amount": 10000.0,
          "gst_amount": 5000.0,
          "tax_amount": 0.0,
          "paid_amount": 0.0,
          "payment_status": "unpaid",
          "phonepay_transaction_id": ""
        },
        "status": "created"
      },
      {
        "event_id": "debe8aca-0313-4635-8732-592f7bcb1e61",
        "event_name": "ac test 2",
        "event_theme_name": "Wedding",
        "order_id": "",
        "payment_details": {
          "total_amount": 10000.0,
          "gst_amount": 5000.0,
          "tax_amount": 0.0,
          "paid_amount": 0.0,
          "payment_status": "unpaid",
          "phonepay_transaction_id": ""
        },
        "status": "created"
      }
    ],
    "pagination": {
      "total": 2,
      "page": 1,
      "page_size": 15,
      "total_pages": 1
    }
  }
}
```
