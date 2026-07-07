from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Table
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

# Many-to-many for likes
likes_table = Table(
    'likes', Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('post_id', Integer, ForeignKey('posts.id'), primary_key=True),
)

# Many-to-many for categories
post_categories = Table(
    'post_categories', Base.metadata,
    Column('post_id', Integer, ForeignKey('posts.id'), primary_key=True),
    Column('category_id', Integer, ForeignKey('categories.id'), primary_key=True)
)

class Category(Base):
    __tablename__ = 'categories'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(255), nullable=False)  # plain for prototype

    posts = relationship("Post", back_populates="author")
    liked_posts = relationship("Post", secondary=likes_table, back_populates="liked_by")

class Post(Base):
    __tablename__ = 'posts'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    like_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    media_type = Column(String(20), default='text')  # text, image, video, mixed

    author = relationship("User", back_populates="posts")
    liked_by = relationship("User", secondary=likes_table, back_populates="liked_posts")
    categories = relationship("Category", secondary=post_categories)