from typing import List
from pydantic import BaseModel
from datetime import datetime

class UserCreate(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str

class PostCreate(BaseModel):
    content: str
    categories: List[str] = []
    media_type: str = "text"

class PostCreateResponse(BaseModel):
    id: int

class PostResponse(BaseModel):
    id: int
    user_id: int
    content: str
    created_at: datetime
    like_count: int
    is_liked: bool = False
    categories: List[str] = []

    class Config:
        from_attributes = True

class UserLikesResponse(BaseModel):
    liked_post_ids: List[int]
    liked_categories: List[str]
