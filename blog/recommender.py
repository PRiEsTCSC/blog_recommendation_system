from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

from blog.models import User
from .database import DB
from .models import Post
from typing import List
from sqlalchemy.orm import selectinload

class Recommender:
    def __init__(self, db: DB):
        self.db = db

    def get_personalized_feed(self, user_id: int, limit: int = 20) -> List[dict]:
        """
        Docstring for get_personalized_feed
        
        :param self: Description
        :param user_id: Description
        :type user_id: int
        :param limit: Description
        :type limit: int
        :return: Description
        :rtype: List[dict[Any, Any]]
        """

        # First things first we check if the user exists
        #TODO: Remove this later, it is unnecessary
        # user: User | None = self.db.get_user_by_id(user_id)
        # if not user:
        #     return self.get_popular_feed(limit)

        
        # Getting the IDs of a user's liked posts
        liked_ids: List[int] = self.db.get_user_liked_post_ids(user_id)


        if not liked_ids:
            return self.get_popular_feed(limit)
        # if there is no like ids then get popular feed for the user


        # Get liked posts with categories for a particular user based on the liked_ids gotten earlier from the previous db query
        with self.db.get_session() as session:
            liked_posts: List[Post] = session.query(Post).options(selectinload(Post.categories))\
                .filter(Post.id.in_(liked_ids)).all()
            # This liked_posts returned the posts object 


        if not liked_posts:
            return self.get_popular_feed(limit)
        # if there is no like ids then get popular feed for the user


        # Loads 300 Candidate Posts from DB with Categories pre-loaded to avoid N+1 queries
        with self.db.get_session() as session:
            all_posts: List[Post] = session.query(Post).options(selectinload(Post.categories))\
                .order_by(Post.created_at.desc()).limit(300).all()


        documents = []
        for p in all_posts:
            cats = " ".join([c.name for c in p.categories]) # here we get all the posts categories and post text content
            documents.append(f"{p.content} {cats}")

        if not documents:
            return [self._post_to_dict(p) for p in all_posts[:limit]] # if the document list generation fails, fall back to converting the all_posts to a dict and then return them like that

        vectorizer = TfidfVectorizer(stop_words='english', max_features=500) # init the vectorizer
        tfidf_matrix = vectorizer.fit_transform(documents) 
        '''Above is there the vectorizer learns the vocabulary and idf, return document-term matrix. The IDF here means Inverse Document Frequency
            Where the common words get a lower score (weight) and the least, very informative ones get a higher weight'''


        # Build user profile (fixed sparse matrix handling)
        user_vectors = []
        for liked in liked_posts: # The liked variable here would contain the liked post object
            for idx, p in enumerate(all_posts): # tuple (number, post object)
                if p.id == liked.id: # type: ignore
                    user_vectors.append(tfidf_matrix[idx].toarray()[0]) # type: ignore
                    break

        if not user_vectors:
            return self.get_popular_feed(limit)

        user_profile = np.mean(user_vectors, axis=0).reshape(1, -1)
        similarities = cosine_similarity(user_profile, tfidf_matrix).flatten()

        # Score and rank
        scored = []
        for i, post in enumerate(all_posts):
            score = float(similarities[i]) * 0.7 + (post.like_count * 0.015)
            scored.append((score, post))

        scored.sort(reverse=True, key=lambda x: x[0])
        recommended = [self._post_to_dict(p) for _, p in scored[:limit]]
        
        return recommended

    def get_popular_feed(self, limit: int = 20) -> List[dict]:
        with self.db.get_session() as session:
            posts = session.query(Post).options(selectinload(Post.categories))\
                .order_by(Post.like_count.desc(), Post.created_at.desc()).limit(limit).all()
            return [self._post_to_dict(p) for p in posts]

    def _post_to_dict(self, post: Post) -> dict:
        return {
            "id": post.id,
            "user_id": post.user_id,
            "content": post.content,
            "created_at": post.created_at,
            "like_count": post.like_count,
            "categories": [c.name for c in getattr(post, 'categories', [])],
            "is_liked": False
        }