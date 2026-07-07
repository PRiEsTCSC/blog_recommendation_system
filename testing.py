from datetime import datetime
from blog.models import Category, Post


sample_content = [
    {
        "id": 7,
        "user_id": 3,
        "content": "I absolutely love building web apps with FastAPI and SQLAlchemy. The performance is amazing!",
        "created_at": "2026-07-04T14:30:00Z",
        "like_count": 24,
        "categories": ["python", "webdev", "fastapi"],
        "is_liked": True,
    },
    {
        "id": 12,
        "user_id": 8,
        "content": "Just finished a new machine learning project using scikit-learn. TF-IDF and cosine similarity work great for recommendations!",
        "created_at": "2026-07-05T09:15:00Z",
        "like_count": 41,
        "categories": ["machinelearning", "datascience", "python"],
        "is_liked": True,
    },
    {
        "id": 45,
        "user_id": 3,
        "content": "Anyone else obsessed with building side projects? Nothing beats the feeling of shipping something cool.",
        "created_at": "2026-07-06T18:45:00Z",
        "like_count": 19,
        "categories": ["sideprojects", "motivation"],
        "is_liked": True,
    },
]

liked_posts = [
    # Post 1
    Post(
        id=7,
        user_id=3,
        content="I absolutely love building web apps with FastAPI and SQLAlchemy. The performance is amazing!",
        created_at=datetime(2026, 7, 4, 14, 30, 0),
        like_count=24,
        media_type='text',
        categories=[                  # ← This relationship is pre-loaded thanks to selectinload
            Category(id=1, name='python'),
            Category(id=5, name='webdev'),
            Category(id=12, name='fastapi')
        ]
    ),

    # Post 2
    Post(
        id=12,
        user_id=8,
        content="Just finished a new machine learning project using scikit-learn. TF-IDF and cosine similarity work great for recommendations!",
        created_at=datetime(2026, 7, 5, 9, 15, 0),
        like_count=41,
        media_type='text',
        categories=[
            Category(id=3, name='machinelearning'),
            Category(id=8, name='datascience'),
            Category(id=1, name='python')
        ]
    ),

    # Post 3
    Post(
        id=45,
        user_id=3,
        content="Anyone else obsessed with building side projects? Nothing beats the feeling of shipping something cool.",
        created_at=datetime(2026, 7, 6, 18, 45, 0),
        like_count=19,
        media_type='text',
        categories=[
            Category(id=9, name='sideprojects'),
            Category(id=15, name='motivation')
        ]
    )
]


for idx, liked in enumerate(liked_posts):
    print(f"idx: {idx}        liked: {liked}")