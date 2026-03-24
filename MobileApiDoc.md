# Mobile APIS 

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






