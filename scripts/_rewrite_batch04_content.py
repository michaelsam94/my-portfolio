"""Aggregate all batch-04 post content."""
from _rewrite_batch04_content_p1 import POSTS_P1
from _rewrite_batch04_content_p2 import POSTS_P2
from _rewrite_batch04_content_p3 import POSTS_P3
from _rewrite_batch04_content_p4 import POSTS_P4
from _rewrite_batch04_content_p5 import POSTS_P5

POSTS = {}
POSTS.update(POSTS_P1)
POSTS.update(POSTS_P2)
POSTS.update(POSTS_P3)
POSTS.update(POSTS_P4)
POSTS.update(POSTS_P5)
