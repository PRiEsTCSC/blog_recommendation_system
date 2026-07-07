# Blog Recommendation System

## Note that the main purpose of this project is the Blog Recommendation, the User management and Post creation can be altered as you like as they are not standard in any form



<br><br>


**Base Url**
- Host: `http://127.0.0.1:8000`

## How to run
```bash
uvicorn blog.main:app --reload --port 8000
```

## How to get the proper Documentation with Swagger UI 
```bash
http://127.0.0.1:8000/docs/
```
<br><br>

## Endpoints

### POST /users/
**Create a new user.**

**Request**
- JSON body: `UserCreate`

**Example Request**
```bash
curl -X POST "http://127.0.0.1:8000/users/" \
  -H "Content-Type: application/json" \
  -d '{"username":"user1","password":"pass123"}'
```

**Successful Response**
- Typically 200 (the code returns the created object; script expects 201)

**Example Response**
```json
{
  "id": 1,
  "username": "user1"
}
```

**Error Responses**
- **400 Bad Request**
  ```json
  {
    "detail": "400 Bad Request: <error message from server>"
  }
  ```

### POST /posts/
**Create a post for an existing user.**

**Query Params**
- `user_id` (int, required)

**Request**
- JSON body: `PostCreate`

**Example Request**
```bash
curl -X POST "http://127.0.0.1:8000/posts/?user_id=1" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Hello world",
    "categories": ["tech","python"],
    "media_type": "text"
  }'
```

**Successful Response**
```json
{
  "id": 10,
  "user_id": 1,
  "content": "Hello world",
  "created_at": "2026-07-04T14:30:00Z",
  "like_count": 0,
  "is_liked": false,
  "categories": ["tech","python"]
}
```

**Error Responses**
- **404 Not Found** (when `user_id` does not exist)
  ```json
  {
    "detail": "User not found"
  }
  ```

### GET /feed/
**General feed: returns most popular posts.**

**Query Params**
- `limit` (int, optional, default=20)

**Successful Response**
- Array of `PostResponse`

**Example Response**
```json
[
  {
    "id": 10,
    "user_id": 1,
    "content": "Hello world",
    "created_at": "2026-07-04T14:30:00Z",
    "like_count": 7,
    "is_liked": false,
    "categories": ["tech","python"]
  }
]
```

### GET /feed/personal/
**Personalized feed for a user.**

**Logic:**
- If user missing: fallback to popular feed
- If user has no likes: fallback to popular feed
- Otherwise:
  - Build TF-IDF vectors from liked posts + categories
  - Score candidate posts using cosine similarity
  - Final score = similarity * 0.7 + like_count * 0.015
  - Adds `is_liked` based on user’s likes

**Query Params**
- `user_id` (int, required)
- `limit` (int, optional, default=20)

**Successful Response**
- Array of `PostResponse`

### POST /posts/{post_id}/like/
**Toggle like/unlike for a post (like_count increments/decrements).**

**Path Params**
- `post_id` (int, required)

**Query Params**
- `user_id` (int, required)

**Example Request**
```bash
curl -X POST "http://127.0.0.1:8000/posts/12/like/?user_id=1"
```

**Successful Response (200)**
```json
{
  "liked": true,
  "like_count": 42
}
```

**Error Responses**
- **404 Not Found**
  ```json
  {
    "detail": "Post not found"
  }
  ```

### GET /users/{user_id}/likes/
**Get liked post IDs and aggregated liked categories.**

**Path Params**
- `user_id` (int, required)

**Successful Response**
```json
{
  "liked_post_ids": [12, 45],
  "liked_categories": ["python", "fastapi", "sideprojects"]
}
```

**Error Responses**
- **404 Not Found** (when user doesn’t exist)
  ```json
  {
    "detail": "User not found"
  }
  ```

## Sample Response Payloads

### A) PostResponse example (feed item)
```json
{
  "id": 10,
  "user_id": 1,
  "content": "My first post!",
  "created_at": "2026-07-04T14:30:00Z",
  "like_count": 7,
  "is_liked": false,
  "categories": ["tech","python"]
}
```

### B) Toggle like response
```json
{
  "liked": true,
  "like_count": 42
}
```

### C) User likes response
```json
{
  "liked_post_ids": [12, 45],
  "liked_categories": ["python", "machinelearning"]
}
```

## Usage Guide / Seed Community

A ready-to-run script is in:
- `usage/community_test.py`

**What it does:**
1. Creates users (user1..user5)
2. Creates posts with randomized categories
3. Randomly toggles likes between users and posts
4. Fetches personalized feed for first 3 users

**Run:**
```bash
python usage/community_test.py
```

## Notes / Implementation Details

- Many endpoints use trailing slashes:
  - `/users/`
  - `/posts/`
  - `/feed/`
  - `/feed/personal/`
- Create Post and Like toggle require query parameter `user_id`.
- The service uses SQLite at `data/app.db` (created automatically).
