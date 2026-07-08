# Recommender Analysis: Stage-by-Stage Breakdown

## STAGE 1: User existence check (redundant DB call)

### Code
```python
# recommender.py (lines 24-28)
user: User | None = self.db.get_user_by_id(user_id)
if not user:
    return self.get_popular_feed(limit)
```

### What's happening
- You make a SQL query to the `users` table to check if user `user_id` exists
- If the user doesn't exist, you return the popular feed instead

### The issue
- **UNNECESSARY DB ROUND-TRIP**: The code itself admits this: `#TODO: Remove this later, it is unnecessary`
- The very next thing you do is `get_user_liked_post_ids(user_id)` — if the user doesn't exist in the likes table, that query returns an empty list, and the code already handles that by falling back to `get_popular_feed`
- You're hitting the database one extra time on **every single request** for no benefit

### The resolution
- **Delete this block entirely**. Let the empty liked_ids check (Stage 2) handle the fallback.

---

## STAGE 2: Getting liked post IDs

### Code
```python
# recommender.py (line 31)
liked_ids: List[int] = self.db.get_user_liked_post_ids(user_id)
```

### What's happening
- Queries the `likes` join table to get all post IDs that `user_id` has liked
- Returns a list like `[1, 5, 12, 44]`

### The issue
- **SEPARATE DB SESSION**: This opens its own database session, closes it, then Stage 3 opens another session
- You could fold this into Stage 3's query with a join, avoiding the round-trip
- Minor issue, but adds up under load

### The resolution
- Merge this query into the next stage's session
- Instead of: get IDs → then get posts by those IDs, you can do: get posts directly via a join

---

## STAGE 3: Empty liked-IDs check (fallback)

### Code
```python
# recommender.py (lines 34-35)
if not liked_ids:
    return self.get_popular_feed(limit)
```

### What's happening
- If the user has never liked anything, `liked_ids` is `[]`
- Falls back to the popular feed — this is correct behavior for new users

### The issue
- **NONE** — This is correct logic. If a user has no likes, there's nothing to build a profile from.

### The resolution
- Keep as-is, or fold into Stage 2's combined query

---

## STAGE 4: Loading liked posts with categories

### Code
```python
# recommender.py (lines 38-41)
with self.db.get_session() as session:
    liked_posts: List[Post] = session.query(Post).options(selectinload(Post.categories))\
        .filter(Post.id.in_(liked_ids)).all()
```

### What's happening
- Opens **another** DB session
- Queries the `posts` table for all posts whose ID is in `liked_ids`
- Uses `selectinload` to eagerly load categories (prevents N+1 queries later)
- Result: you now have the full Post objects (content, categories, like_count, etc.) for all liked posts

### The issue
- **SEPARATE SESSION from Stage 2** (minor inefficiency)
- **POTENTIAL PERFORMANCE**: If a user has 500 liked posts, this returns 500 posts loaded into memory with their categories

### The resolution
- Merge with Stage 2 into a single query using a join on the likes table
- Example:
  ```python
  with self.db.get_session() as session:
      liked_posts = session.query(Post).options(selectinload(Post.categories))\
          .join(likes_table, Post.id == likes_table.c.post_id)\
          .filter(likes_table.c.user_id == user_id).all()
  ```
  This skips the intermediate IDs query entirely.

---

## STAGE 5: Empty liked-posts check (another fallback)

### Code
```python
# recommender.py (lines 44-46)
if not liked_posts:
    return self.get_popular_feed(limit)
```

### What's happening
- Guards against the `id.in_(liked_ids)` returning nothing (e.g., posts were deleted after being liked)

### The issue
- **NONE** — Defensive check, reasonable to keep

### The resolution
- Keep it

---

## STAGE 6: Loading candidate posts (the "pool" to recommend from)

### Code
```python
# recommender.py (lines 49-52)
with self.db.get_session() as session:
    all_posts: List[Post] = session.query(Post).options(selectinload(Post.categories))\
        .order_by(Post.created_at.desc()).limit(300).all()
```

### What's happening
- Opens **YET ANOTHER** DB session
- Loads the 300 most recent posts (ordered by `created_at` descending)
- Eagerly loads categories
- These 300 posts are the "candidate pool" — the system will only recommend from these 300

### The issue
- **HARDCODED MAGIC NUMBER**: `300` is plucked from thin air — why 300? Why not 100? 1000?
- **RECENCY BIAS**: Only the latest 300 posts are considered. If a user's liked posts are all older than the newest 300 posts, NONE of their liked posts will be in this candidate pool. This means:
  - Stage 7's mapping will find NOTHING
  - `user_vectors` will be empty
  - The code falls back to `get_popular_feed`
  - **The user NEVER gets personalized recommendations if their likes are old**
- **SEPARATE SESSION**: 4th session opened so far

### The resolution
- Make 300 a configurable parameter (`candidate_pool_size`)
- Increase the pool size significantly OR use a smarter retrieval strategy
- Merge into a single session with the other queries

---

## STAGE 7: Building text documents for TF-IDF

### Code
```python
# recommender.py (lines 54-58)
documents = []
for p in all_posts:
    cats = " ".join([c.name for c in p.categories])
    documents.append(f"{p.content} {cats}")
```

### What's happening
- For each of the 300 candidate posts, you create a string combining:
  - The post's `content` (the actual article/blog text)
  - The names of all categories (e.g., "technology python programming")
- Result: `documents` is a list of 300 strings like:
  ```
  "Python is a great language for data science technology python programming"
  ```

### The issue
- **CATEGORIES DILUTED IN CONTENT**: Categories like "technology", "python" are short words mixed into long content. Their influence depends on frequency — if "technology" appears in the content AND in the category string, it gets double-counted. You can't tune "category importance" separately from "content importance".
- **MEDIA TYPE IGNORED**: The schema has a `media_type` field (text, image, video). If a post is an image with empty content, its document is just `" "` — meaningless. The system can't learn from it.

### The resolution
- Use separate vectorizers for content and categories (Stage 11 detail)
- For image/video posts, consider using the category text as the primary signal rather than empty content

---

## STAGE 8: Fitting the TF-IDF vectorizer (MAJOR ISSUE)

### Code
```python
# recommender.py (lines 60-61)
vectorizer = TfidfVectorizer(stop_words='english', max_features=500)
tfidf_matrix = vectorizer.fit_transform(documents)
```

### What's happening
- Creates a **new** TF-IDF vectorizer from scratch
- `.fit_transform(documents)` does TWO things:
  1. **FIT**: Learns the vocabulary (which 500 words to track) and calculates IDF weights (how rare/informative each word is)
  2. **TRANSFORM**: Converts the 300 documents into a 300×500 numerical matrix where each document becomes a vector of 500 numbers

### The issue — **THIS IS THE BIGGEST PROBLEM**
```
Request 1:  User A requests feed
└─ fit_transform on posts 5000-4700 → learns vocab + IDF from THESE 300 posts
    └─ Scores calculated using THIS vocabulary

Request 2:  User B requests feed (new posts added)
└─ fit_transform on posts 5020-4720 → learns DIFFERENT vocab + IDF from DIFFERENT 300 posts
    └─ Scores calculated using DIFFERENT vocabulary

→ The same post can get DIFFERENT scores on different requests
→ Because the vocabulary and IDF weights change every time
```

**Concrete example:**
- Request A: candidate pool contains 5 posts about "Python". IDF for "python" is low (common).
- Request B: candidate pool contains only 1 post about "Python". IDF for "python" is high (rare).
- Same post, same user → different similarity score. **The recommendations are non-deterministic.**

Also: **fit_transform is EXPENSIVE** — it's doing NLP work (tokenization, counting, IDF calculation) on every request. This is CPU-heavy.

### The resolution
- **Pre-fit the vectorizer ONCE** (e.g., on all historical posts, or a representative sample)
- **Cache it** (store on the Recommender instance, or serialize to disk)
- On each request, only call `.transform(documents)` — which is much cheaper (just matrix multiplication)
  ```python
  # Fitted once at startup (or on a schedule)
  vectorizer = TfidfVectorizer(stop_words='english', max_features=500)
  vectorizer.fit(all_historical_documents)  # do this once
  
  # Per request:
  tfidf_matrix = vectorizer.transform(documents)  # just transform, no fitting
  ```

---

## STAGE 9: Building the user profile (THE NESTED LOOP PROBLEM)

### Code
```python
# recommender.py (lines 64-70)
user_vectors = []
for liked in liked_posts:           # For EACH liked post
    for idx, p in enumerate(all_posts):  # Search through ALL 300 candidates
        if p.id == liked.id:             # Find if this liked post is in candidates
            user_vectors.append(tfidf_matrix[idx].toarray()[0])  # Convert to dense
            break                        # Found it, move to next liked
```

### What's happening
- You want to find the vector representation of each liked post from the TF-IDF matrix
- But to find which ROW in the matrix corresponds to each liked post, you linearly search through `all_posts` for a matching ID
- When found, you call `.toarray()[0]` to convert the sparse matrix row into a dense Python list

### The issue — **NESTED LOOPS + REPEATED DENSE CONVERSION**

```python
# If user has 50 liked posts, and candidate pool = 300:
# Outer loop: 50 iterations
# Inner loop: up to 300 iterations per outer iteration
# Total comparisons: up to 50 × 300 = 15,000
```

**15,000 comparisons** every time someone requests a personalized feed.

Plus `.toarray()` creates a full dense vector (500 floats) every time. Doing this 50 times = 50 separate dense allocations.

**But there's a WORSE correctness bug:**

```python
# If liked_posts = [Post(id=1), Post(id=2), Post(id=1000)]
# And all_posts = [Post(id=500), Post(id=499), ..., Post(id=201)]
#                          ↑ only the latest 300 posts
# Post(id=1000) is NOT in all_posts → the inner loop NEVER finds a match
# Post(id=1) is NOT in all_posts → same, never found
# user_vectors = []  ← EMPTY!
# Falls back to popular feed!
```

**If a user's liked posts are old (outside the 300 newest), they get ZERO personalized recommendations. The system silently fails to personal feed and gives them popular instead.**

### The resolution

```python
# Build a map ONCE: post_id → row_index
id_to_idx = {p.id: i for i, p in enumerate(all_posts)}  # {500: 0, 499: 1, 498: 2, ...}

# Now find liked post indices in O(liked_posts) instead of O(liked_posts * all_posts)
liked_indices = [id_to_idx[l.id] for l in liked_posts if l.id in id_to_idx]
#                                          ^^^^^^^^^^^^^^^^
# Posts outside the candidate pool are EXPLICITLY excluded
# No silent fallback — you KNOW which liked posts contribute

# Then get all vectors at once (sparse operation, no toarray in loops)
user_vectors = tfidf_matrix[liked_indices]  # still sparse
```

**Map lookup is O(1)** instead of O(300). The 15,000 comparisons become at most 50 lookups.

---

## STAGE 10: Computing the user profile vector

### Code
```python
# recommender.py (lines 72-73)
user_profile = np.mean(user_vectors, axis=0).reshape(1, -1)
```

### What's happening
- Takes the average of all liked post vectors to create a single "user preference" vector
- `.reshape(1, -1)` makes it a 1×500 matrix (for cosine_similarity which expects 2D input)
- This average vector represents "the typical post this user likes"

### The issue
- **NO TIME WEIGHTING**: A post liked 2 years ago contributes equally to a post liked yesterday. People's interests change.
- **NO SPARSE OPTIMIZATION**: `np.mean()` on a list of dense arrays is OK, but could be done in sparse form

### The resolution
- For now, it's acceptable for a prototype
- Long-term: add time-decay weighting (requires schema change to store like timestamps)

---

## STAGE 11: Computing similarity scores

### Code
```python
# recommender.py (line 74)
similarities = cosine_similarity(user_profile, tfidf_matrix).flatten()
```

### What's happening
- Compares the user profile vector (1×500) against ALL 300 candidate post vectors (300×500)
- Uses cosine similarity: measures the angle between vectors (1.0 = identical, 0.0 = no relation)
- Returns 300 similarity scores (one per candidate post)
- `.flatten()` converts from `[[0.2, 0.5, 0.1, ...]]` to `[0.2, 0.5, 0.1, ...]`

### The issue
- **NONE** — this is correct usage of cosine_similarity
- It's the scoring stage that has the problem (Stage 12)

### The resolution
- Keep as-is

---

## STAGE 12: Blending similarity + popularity (THE UNNORMALIZED BLEND)

### Code
```python
# recommender.py (lines 77-81)
scored = []
for i, post in enumerate(all_posts):
    score = float(similarities[i]) * 0.7 + (post.like_count * 0.015)
    scored.append((score, post))
```

### What's happening
- For each post, calculates a final score:
  ```
  final_score = content_similarity × 0.7 + like_count × 0.015
  ```
- `0.7` and `0.015` are weights (magic numbers)
- The goal: blend "posts similar to what you like" (70%) with "popular posts" (1.5% per like)

### The issue — **COMPLETELY UNBALANCED SCALES**

```python
# Case 1: Post with high similarity but low likes
similarity = 0.80  (high match!)
like_count  = 2    (new post, few likes)
score = 0.80 × 0.7 + 2 × 0.015
     = 0.56       + 0.03
     = 0.59

# Case 2: Post with barely any similarity but high likes
similarity = 0.05  (bad match!)
like_count  = 100  (viral post)
score = 0.05 × 0.7 + 100 × 0.015
     = 0.035      + 1.5
     = 1.535
```

**The viral post scores 2.6× higher than the relevant post/home/the_priest/myenv/bin/activate* The "personalized" feed is actually driven by raw popularity, not personalization. `like_count * 0.015` is not a percentage — `0.015` is just a number that happened to be chosen. With 1000 likes, that term becomes `15.0`.

### The resolution

**Normalize `like_count` first** so it's on a similar scale to cosine similarity (0.0–1.0):

```python
# Option A: Log normalization (compresses large counts)
log_likes = np.log1p([p.like_count for p in all_posts])  # log(1+like_count)
max_log = max(log_likes) if log_likes else 1
normalized_likes = log_likes / max_log  # now 0.0 to 1.0

# Option B: Min-max scaling within candidate set
like_counts = np.array([p.like_count for p in all_posts])
min_lc, max_lc = like_counts.min(), like_counts.max()
if max_lc > min_lc:
    normalized_likes = (like_counts - min_lc) / (max_lc - min_lc)
else:
    normalized_likes = np.zeros_like(like_counts)

# Then: both terms are 0.0–1.0, weights actually mean something
score = similarities[i] * 0.7 + normalized_likes[i] * 0.3
```

Now `0.7` and `0.3` mean "70% from content match, 30% from popularity" — the weights actually reflect what you intend.

---

## STAGE 13: Sorting and returning (the final output)

### Code
```python
# recommender.py (lines 83-85)
scored.sort(reverse=True, key=lambda x: x[0])
recommended = [self._post_to_dict(p) for _, p in scored[:limit]]
return recommended
```

### What's happening
- Sorts all scored posts by score (highest first)
- Takes the top `limit` (default 20)
- Converts Post objects to dictionaries using `_post_to_dict`
- Returns the list

### The issue
- **NO TIE-BREAKING**: If two posts have identical scores, Python's sort is "stable" (keeps original order), but that order depends on how the database returned them. Ties could be resolved differently across requests.
- **DETERMINISTIC ORDERING**: Not critical but nice to have

### The resolution
- Add tie-breakers:
  ```python
  scored.sort(reverse=True, key=lambda x: (x[0], x[1].created_at, x[1].id))
  ```

---

## STAGE 14: `_post_to_dict` (the output format)

### Code
```python
# recommender.py (lines 92-101)
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
```

### What's happening
- Converts a Post ORM object to a plain dictionary for JSON serialization
- `getattr(post, 'categories', [])` is defensive: if categories weren't eager-loaded, it returns `[]` instead of crashing

### The issue
- **`is_liked` is ALWAYS `False`**: This method always sets `is_liked=False`. The actual `is_liked` value is set AFTER the recommender returns, in `main.py`:
  ```python
  # main.py line 72-73
  for p in posts_dicts:
      p["is_liked"] = p["id"] in liked_ids
  ```
  So there's a split responsibility — recommender says "not liked", main overrides it. Confusing ownership.
- **`getattr` is slightly defensive**: Since ALL callers use `selectinload(Post.categories)`, the categories are always loaded. But if someone calls this without eager loading, it silently returns no categories rather than erroring.

### The resolution
- Either: pass `liked_ids` into the recommender and have it set `is_liked` correctly
- Or: remove `is_liked` from the recommender entirely and only set it in `main.py` (document this clearly)
- Keep `getattr` or remove it — either is defensible

---

## Summary of the 4 biggest issues (the ones that actually matter)

### Issue 1: TF-IDF fitted every request (Stage 8)
- **Problem**: CPU-heavy, non-stationary scores
- **Fix**: Fit once at startup, cache the vectorizer, use `.transform()` per request

### Issue 2: Nested loop for liked post → matrix index (Stage 9)
- **Problem**: O(N²) comparisons + repeated dense allocation + silent exclusion of old liked posts
- **Fix**: Use `id_to_idx` dictionary, bulk sparse indexing

### Issue 3: Unnormalized like_count in scoring (Stage 12)
- **Problem**: Popularity term dominates similarity term, "personalized" feed is actually "viral" feed
- **Fix**: Normalize like_count to 0–1 before blending

### Issue 4: Silently fall back to popular when liked posts are outside candidate pool (Stage 9 + Stage 6)
- **Problem**: If a user's likes are old (outside the newest 300 posts), they never get personal recommendations
- **Fix**: Use a larger candidate pool, or flag when liked posts aren't found so you can compensate

These 4 issues are the highest ROI fixes. The others (magic numbers, separate vectorizers, session consolidation, etc.) are refinements for after these are addressed.
