import requests
import random
import time
from typing import List

BASE_URL = "http://127.0.0.1:8000"

def create_user(username: str, password: str = "pass123"):
    response = requests.post(f"{BASE_URL}/users/", json={"username": username, "password": password})
    if response.status_code == 201:
        print(f"Created user: {username} (ID: {response.json()['id']})")
        return response.json()['id']
    else:
        print(f"Failed to create {username}: {response.text}")
        return None

def create_post(user_id: int, content: str, categories: List[str], media_type: str = "text"):
    response = requests.post(
        f"{BASE_URL}/posts/?user_id={user_id}",
        json={"content": content, "categories": categories, "media_type": media_type}
    )
    if response.status_code == 201:
        post = response.json()
        print(f"Created post {post['id']} by user {user_id}")
        return post['id']
    else:
        print(f"Failed post for user {user_id}: {response.text}")
        return None

def like_post(user_id: int, post_id: int):
    response = requests.post(f"{BASE_URL}/posts/{post_id}/like/?user_id={user_id}")
    if response.status_code == 200:
        result = response.json()
        print(f"User {user_id} {'liked' if result['liked'] else 'unliked'} post {post_id}")
        return result['liked']
    return False

def get_personal_feed(user_id: int):
    response = requests.get(f"{BASE_URL}/feed/personal/?user_id={user_id}&limit=10")
    if response.status_code == 200:
        print(f"\nPersonal feed for user {user_id}:")
        for post in response.json():
            print(f"  - Post {post['id']}: {post['content'][:60]}... | Likes: {post['like_count']} | Liked: {post['is_liked']}")
    else:
        print("Failed to get feed")

def seed_community():
    print("=== Seeding Community ===")
    
    # Create users
    users = []
    for i in range(1, 6):
        username = f"user{i}"
        uid = create_user(username)
        if uid:
            users.append(uid)
        time.sleep(0.2)

    if not users:
        return

    # Categories pool
    categories_pool = ["tech", "sports", "food", "travel", "science", "music", "fitness"]

    # Create posts
    posts = []
    sample_contents = [
        "Excited about the new AI breakthroughs in 2026!",
        "Just finished an amazing hike in the mountains.",
        "Best pizza recipe ever - you have to try this!",
        "What are your thoughts on quantum computing?",
        "My workout routine for building strength.",
        "Beautiful sunset at the beach today.",
        "Latest gadget review - this one is a game changer."
    ]

    for user_id in users:
        for _ in range(3):  # 3 posts per user
            content = random.choice(sample_contents)
            cats = random.sample(categories_pool, k=random.randint(1, 3))
            post_id = create_post(user_id, content, cats)
            if post_id:
                posts.append(post_id)
            time.sleep(0.1)

    # Random likes - simulate engagement
    for _ in range(30):  # 30 likes
        user_id = random.choice(users)
        post_id = random.choice(posts)
        like_post(user_id, post_id)
        time.sleep(0.05)

    # Get feeds for a few users
    print("\n=== Checking Personalized Feeds ===")
    for user_id in users[:3]:
        get_personal_feed(user_id)
        time.sleep(1)

    print("\n=== Community seeded successfully! ===")

if __name__ == "__main__":
    seed_community()