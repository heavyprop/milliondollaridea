# User Interests

This file explains what we have implemented so far for calculating user interests.

We are not recommending posts yet. Right now we are only building a user interest profile.

## What We Have Done

Each post is classified when it is created.

The post stores tags in `Thread.topic_labels`.

Example:

```json
[
  {
    "id": "379",
    "label": "Technology & Computing",
    "score": 0.18,
    "rank": 1
  }
]
```

The current classifier in `apps/recommendations/classification.py` keeps the top cosine-similarity scores and clamps negative scores to zero. It does not normalize their sum to `1`.

## Raw User Data We Save

We save raw user actions in the database.

Current tables:

```text
ThreadView      -> user viewed a post and total seconds viewed
ThreadLike      -> user liked a post
CommentLike     -> user liked a comment
Comment         -> user commented on a post
Thread          -> user created a post
```

We do not save final `user_interests` to the database yet.

Instead, we calculate them when needed from the raw actions.

## User Interest Calculation

The calculation lives in:

```text
apps/recommendations/interests.py
```

The main function is:

```python
build_user_interests(user)
```

It returns a dictionary like:

```json
{
  "379": {
    "label": "Technology & Computing",
    "weight": 8.4
  },
  "150": {
    "label": "Cars",
    "weight": 5.2
  }
}
```

Higher `weight` means the user is more interested in that tag.

## Current Weights

```text
View post:              0.25 x min(seconds / 30, 2)
Like comment:           1.0
Like post:              3.0
Comment on post:        4.0
Create post:            5.0
```

## How A Tag Gets Added

For every user action, we look at the post's tags.

For each tag:

```text
user_interest[tag_id] += post_tag_score x action_weight x decay
```

If the tag does not exist in the user's profile yet, it starts at `0`.

Example:

```text
post tag: cars = 0.40
action: user liked post
like weight: 3.0
decay: 1.0

cars += 0.40 x 3.0 x 1.0
cars += 1.2
```

## Event-Based Decay

We use event-based decay, not time-based decay.

The newest action gets the strongest value.

Older actions get weaker based on how many user actions happened after them.

Current value:

```python
FORGETTING_FACTOR = 0.95
```

Formula:

```text
decay = 0.95 ^ steps_ago
```

Examples:

```text
Newest action:    0.95 ^ 0  = 1.00
10 actions ago:   0.95 ^ 10 = 0.60
20 actions ago:   0.95 ^ 20 = 0.36
50 actions ago:   0.95 ^ 50 = 0.08
```

This lets the user's interests change over time.

## Limits

Current limits:

```text
MAX_EVENTS = 200
MAX_TAGS = 100
```

This means:

- use the latest 200 user actions
- calculate the interest weights
- keep the top 100 strongest tags

## When It Runs

The homepage currently calls:

```python
build_user_interests(request.user)
```

So user interests are recalculated every time the homepage loads.

## How To Debug

Open Django shell:

```bash
python manage.py shell
```

Then run:

```python
from django.contrib.auth.models import User
from apps.recommendations.interests import print_user_interests

user = User.objects.get(username="Daniel")
print_user_interests(user)
```

Or return the dictionary:

```python
from apps.recommendations.interests import build_user_interests

build_user_interests(user)
```

## What We Need To Do

We still need to build the actual recommendation system.

Needed next:

- Build candidate post selection.
- Compare user interests against post tags.
- Use cosine similarity.
- Add fallback feed for users with no interests.
- Normalize popularity and recency scores.
- Combine scores into a final feed score.
- Display recommended posts on the homepage.

Possible future improvements:

- Add a single `UserEvent` table for cleaner event ordering.
- Cache calculated user interests for performance.
- Ignore very short views.
- Add negative signals.
- Add exploration/random posts so users can discover new topics.
