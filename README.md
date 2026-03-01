# nuvo_web_backend


📦 Project Architecture
```
apps/
│
├── accounts/     → Auth, OTP, JWT, Middleware
├── users/        → Profile & Business Logic
├── common/       → Utilities & Validators
```

## 🔐 Authentication Flow
```
send-otp
    ↓
verify-otp → returns access + refresh
    ↓
Frontend checks /auth/me
    ↓
If profile not completed → call complete-profile
    ↓
Normal app usage
```

### 🌍 Base URL 
`http://127.0.0.1:8000/api/` 

All protected APIs require: 

`Authorization: Bearer <ACCESS_TOKEN> ` 

## 🔐 AUTH APIs 
### 1️⃣ Send OTP 

POST `/auth/send-otp/` 

### Body 
``` 
{
  "email": "user@gmail.com",
  "phone_number": "9999999999",
  "role": "CLIENT"
}
```
### Roles
- CLIENT
- STAFF
- MAKEUP_ARTIST
- ADMIN

### Response
```
{
  "success": true,
  "message": "OTP sent successfully",
  "data": {}
}
```

## 2️⃣ Verify OTP (Login)

POST `/auth/verify-otp/`
### body
```
{
  "email": "user@gmail.com",
  "phone_number": "9999999999",
  "role": "CLIENT",
  "otp": "123456"
}
```
### Response
```
{
  "success": true,
  "message": "Login successful",
  "data": {
    "access_token": ".........",
    "refresh_token": ".........",
    "user": {
      "id": "ee7c55fc-4d49-4aff-b22a-a9df6937a178",
      "email": "rakeshac420@gmail.com",
      "phone_number": "9686045679",
      "role": "CLIENT",
      "status": "ACTIVE",
      "profile_completed": false
    }
  }
}
```

## 3️⃣ Refresh Token

POST `/auth/refresh-token/`
### body
```
{
  "refresh_token": "your_refresh_token"
}
```
Returns new access token.
### Responce 
```
{
  "success": true,
  "message": "Token refreshed successfully",
  "data": {
    "access_token": "......"
  }
}
```



## 4️⃣ Logout

POST `/auth/logout/`

### Header:
`Authorization: Bearer ACCESS_TOKEN`

### Body:
```
{
  "refresh_token": "your_refresh_token"
}
```
Blacklists refresh token.
### Responce 
```
{
  "success": true,
  "message": "Logged out successfully",
  "data": {}
}
```

## 5️⃣ Resend OTP

POST `/auth/resend-otp/`
### Body
```
{
  "email": "user@gmail.com"
}
```
60-second cooldown 5-minute expiry
### Responce
```
{
  "success": true,
  "message": "OTP resent successfully",
  "data": {}
}
```

## 6️⃣ Get Logged-in User

GET `/auth/me/`
### Returns:
```
{
  "success": true,
  "message": "User fetched",
  "data": {
    "id": "0f010853-b7f0-41f1-b2c1-85c257ee3aa0",
    "email": "user@gmail.com",
    "phone_number": "9999999999",
    "role": "CLIENT",
    "status": "ACTIVE",
    "profile_completed": false
  }
}
```


# 👤 PROFILE APIs

## 7️⃣ Complete Client Profile 

POST `/users/complete/client/`
### Body
```
{
  "full_name": "Rakesh AC",
  "city": "Bangalore",
  "state": "Karnataka",
  "country": "India",
  "subscription_plan": "SILVER"
}
```
### Responce 
```
{
  "success": true,
  "message": "Client profile completed",
  "data": {}
}
```


## 8️⃣ Complete Staff Profile

POST `/users/complete/staff/`
### Body
```
{
  "full_name": "Rahul",
  "stage_name": "Rocky",
  "gender": "Male",
  "city": "Chennai",
  "state": "Tamil Nadu",
  "country": "India",
  "price_of_staff": 5000,
  "experience_in_years": 3
}
```


## 9️⃣ Complete Makeup Artist Profile

POST `/users/complete/makeup/`
### Body
```
{
  "full_name": "Anita",
  "gender": "Female",
  "makeup_speciality": "Bridal",
  "city": "Mumbai",
  "state": "Maharashtra",
  "country": "India",
  "experience_in_years": 5
}
```


## 🔟 Get My Profile (Role-Based)

GET `/users/my-profile/`

Returns profile based on role.


## 1️⃣1️⃣ Update My Profile

PUT `/users/update-profile/`

Body depends on role.

## 1️⃣2️⃣ Upload Staff Images

POST `/users/staff/upload-images/`

Form Data:
```
images: file1
images: file2
images: file3
```
Stores locally

Updates gallery_images field


# 👑 ADMIN APIs
## 1️⃣3️⃣ List All Users

GET `/users/admin/all-users/`

Requires role = ADMIN

## 1️⃣4️⃣ Change User Status

PUT `/users/admin/change-status/`
### Body
```
{
  "user_id": "uuid",
  "status": "BLOCKED"
}
```
### Status options:
```
ACTIVE
INACTIVE
BLOCKED
```

## 1️⃣5️⃣ Update Client Subscription

PUT `/users/admin/update-subscription/`
```
{
  "user_id": "uuid",
  "subscription_plan": "GOLD"
}
```
### Plans:
```
SILVER
BRONZE
GOLD
PLATINUM
DIAMOND
```



# Master data apis 
## ✅ Create Event Theme
POST `/master/themes/create/`  
### Body 
```
{
  "theme_name": "Royal Wedding",
  "description": "Classic royal wedding setup with golden decor",
  "cover_image": "https://example.com/cover.jpg",
  "gallery_images": [
    "https://example.com/img1.jpg",
    "https://example.com/img2.jpg"
  ]
}
```
### Responce 
```
{
  "success": true,
  "message": "Theme created",
  "data": {}
}
```

## ✅ List Event Themes 
GET `/master/themes/`
### Responce 
```
{
  "success": true,
  "message": "Themes fetched",
  "data": [
    {
      "id": "uuid",
      "theme_name": "Royal Wedding",
      "status": "ACTIVE",
      "description": "Classic royal wedding setup",
      "cover_image": "https://example.com/cover.jpg",
      "gallery_images": [
        "https://example.com/img1.jpg"
      ]
    }
  ]
}
```


## ✅ Update Event Theme
GET `/master/themes/<theme_id>/update/`
### Body 
```
{
  "theme_name": "Modern Royal Wedding",
  "status": "ACTIVE",
  "description": "Updated description"
}
```
### Responce 
```
{
  "success": true,
  "message": "Theme updated",
  "data": {}
}
```

## ✅ Delete Event Theme
DELETE `/master/themes/<theme_id>/delete/`
### Body 
```
{
  "success": true,
  "message": "Theme deleted",
  "data": {}
}
```
### Responce 
```
{
  "success": true,
  "message": "Theme deleted",
  "data": {}
}
```


## uniform category

## ✅ Create Uniform Category
POST `/master/uniform/create/`

### Body
```
{
  "category_name": "Royal Traditional",
  "unique_key": "royal_traditional",
  "description": "Traditional royal uniforms",
  "images": [
    "https://example.com/u1.jpg",
    "https://example.com/u2.jpg"
  ]
}
```
### Response
```
{
  "success": true,
  "message": "Uniform category created",
  "data": {}
}
```

## ✅ List Uniform Categories
GET `/master/uniform/`
### Response
```
{
  "success": true,
  "message": "Uniform categories fetched",
  "data": [
    {
      "id": "uuid",
      "category_name": "Royal Traditional",
      "unique_key": "royal_traditional",
      "description": "Traditional royal uniforms",
      "images": ["https://example.com/u1.jpg"],
      "is_active": true
    }
  ]
}
```

## 🟡 3️⃣ SUBSCRIPTION PLAN SETTINGS

Plan names are fixed:
```
Diamond
Platinum
Gold
Silver
Bronze
```

## ✅ Update Subscription Plan
PUT `/master/subscription/<plan_name>/update/`
### Example:
`/subscription/Diamond/update/` 
### Body
```
{
  "monthlyPrice": 9999,
  "yearlyPrice": 99999,
  "prioritySupport": true,
  "isFree": false
}
```
### Response
```
{
  "success": true,
  "message": "Subscription plan updated",
  "data": {}
}
```

## 🔵 4️⃣ PAYMENT TERMS

Single document collection.

### ✅ Update Payment Terms
PUT `/master/payment/update/`
### Body
```
{
  "advancePercentage": 30
}
```
### Response
```
{
  "success": true,
  "message": "Payment terms updated",
  "data": {}
}
```

