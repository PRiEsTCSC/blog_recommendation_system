from fastapi import FastAPI, HTTPException
from typing import List

from blog.schemas import PostCreate, PostResponse, UserCreate, UserLikesResponse, UserResponse
from .database import DB
from .recommender import Recommender
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy.orm import selectinload

app = FastAPI(title="Lightning Blog Prototype")
db = DB()
recommender = Recommender(db)

# Helper to safely convert Post to dict
def post_to_response(post):
    return {
        "id": post.id,
        "user_id": post.user_id,
        "content": post.content,
        "created_at": post.created_at,
        "like_count": post.like_count,
        "is_liked": False,
        "categories": [c.name for c in getattr(post, 'categories', [])]
    }

@app.post("/users/", response_model=UserResponse)
def create_user(data: UserCreate):
    try:
        user = db.create_user(data.username, data.password)
        return user
    except Exception as e:
        raise HTTPException(400, str(e))

@app.post("/posts/", response_model=PostResponse)
def create_post(data: PostCreate, user_id: int):
    if not db.get_user_by_id(user_id):
        raise HTTPException(404, "User not found")
    post = db.create_post(user_id, data.content, data.categories, data.media_type)
    return post_to_response(post)

@app.get("/feed/", response_model=List[PostResponse])
def get_general_feed(limit: int = 20):
    posts = db.get_all_posts(limit)
    return [post_to_response(p) for p in posts]

@app.get("/feed/personal/", response_model=List[PostResponse])
def get_personal_feed(user_id: int, limit: int = 20):
    posts_dicts = recommender.get_personalized_feed(user_id, limit)
    liked_ids = db.get_user_liked_post_ids(user_id)
    for p in posts_dicts:
        p["is_liked"] = p["id"] in liked_ids
    return posts_dicts

@app.post("/posts/{post_id}/like/")
def toggle_like(post_id: int, user_id: int):
    try:
        return db.toggle_like(user_id, post_id)
    except ValueError:
        raise HTTPException(404, "Post not found")


@app.get("/users/{user_id}/likes/", response_model=UserLikesResponse)
def get_user_likes(user_id: int):
    """Get all liked post IDs and aggregated liked categories for a user"""
    if not db.get_user_by_id(user_id):
        raise HTTPException(404, "User not found")
    
    # Step 1: Get all post IDs the user has liked
    liked_post_ids = db.get_user_liked_post_ids(user_id)
    
    # Step 2: Get unique categories from those liked posts
    liked_categories = []
    if liked_post_ids:
        with db.get_session() as session:
            from .models import Post
            # Eager load categories to avoid detached instance errors
            posts = session.query(Post).options(selectinload(Post.categories))\
                .filter(Post.id.in_(liked_post_ids)).all()
            
            cat_set = set()
            for post in posts:
                for cat in getattr(post, 'categories', []):
                    cat_set.add(cat.name)
            
            liked_categories = sorted(list(cat_set))  # sorted for consistency
    
    return {
        "liked_post_ids": liked_post_ids,
        "liked_categories": liked_categories
    }
