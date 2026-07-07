from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, Session, selectinload
from .models import Base, User, Post, Category, likes_table
import os
from typing import List, Optional

class DB:
    def __init__(self, db_path: str = "data/app.db"):
        os.makedirs("data", exist_ok=True)
        self.engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)

    def get_session(self) -> Session:
        return self.SessionLocal()

    # Users
    def create_user(self, username: str, password: str) -> User:
        with self.get_session() as session:
            user = User(username=username, password=password)
            session.add(user)
            session.commit()
            session.refresh(user)
            return user

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        with self.get_session() as session:
            return session.get(User, user_id)

    # Categories
    def get_or_create_category(self, name: str) -> Category:
        with self.get_session() as session:
            cat = session.query(Category).filter(Category.name == name.lower()).first()
            if not cat:
                cat = Category(name=name.lower())
                session.add(cat)
                session.commit()
                session.refresh(cat)
            return cat

    # Posts
    def create_post(self, user_id: int, content: str, categories: List[str], media_type: str = 'text') -> Post:
        with self.get_session() as session:
            post = Post(user_id=user_id, content=content, media_type=media_type)
            session.add(post)
            session.commit()
            session.refresh(post)

            for cat_name in categories:
                cat = self.get_or_create_category(cat_name)
                post.categories.append(cat)
            session.commit()
            return post

    def get_all_posts(self, limit=50) -> List[Post]:
        with self.get_session() as session:
            return session.query(Post).options(selectinload(Post.categories))\
                .order_by(Post.created_at.desc()).limit(limit).all()

    def get_user_posts(self, user_id: int, limit=20) -> List[Post]:
        with self.get_session() as session:
            return session.query(Post).options(selectinload(Post.categories))\
                .filter(Post.user_id == user_id)\
                .order_by(Post.created_at.desc()).limit(limit).all()
    # Likes
    def toggle_like(self, user_id: int, post_id: int) -> dict:
        with self.get_session() as session:
            post = session.get(Post, post_id)
            if not post:
                raise ValueError("Post not found")

            stmt = select(likes_table).where(likes_table.c.user_id == user_id, likes_table.c.post_id == post_id)
            exists = session.execute(stmt).first() is not None

            if exists:
                session.execute(likes_table.delete().where(likes_table.c.user_id == user_id, likes_table.c.post_id == post_id))
                post.like_count = max(0, post.like_count - 1) # type: ignore
                liked = False
            else:
                session.execute(likes_table.insert().values(user_id=user_id, post_id=post_id))
                post.like_count += 1 # type: ignore
                liked = True
            session.commit()
            return {"liked": liked, "like_count": post.like_count}

    def get_user_liked_post_ids(self, user_id: int) -> List[int]:
        with self.get_session() as session:
            result = session.execute(select(likes_table.c.post_id).where(likes_table.c.user_id == user_id)).all()
            return [r[0] for r in result]