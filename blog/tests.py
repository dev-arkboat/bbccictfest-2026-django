from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .models import Comment, Like, Post

User = get_user_model()


class BlogListTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(username="author", password="pass12345")
        self.reader = User.objects.create_user(username="reader", password="pass12345")
        self.first = Post.objects.create(
            title="First Story", content="Hello world. " * 50, author=self.author,
            status=Post.STATUS_PUBLISHED, published_at=timezone.now(),
        )
        self.second = Post.objects.create(
            title="Second Story", content="Short one.", author=self.author,
            status=Post.STATUS_PUBLISHED,
            published_at=timezone.now() - timedelta(days=1),
        )
        Post.objects.create(
            title="Hidden Draft", content="Not yet.", author=self.author,
            status=Post.STATUS_DRAFT,
        )
        Like.objects.create(post=self.first, user=self.reader)
        Comment.objects.create(post=self.first, author=self.reader, body="Nice!")
        Comment.objects.create(
            post=self.first, author=self.reader, body="Spam!", is_approved=False
        )

    def test_featured_plus_grid_and_counts(self):
        r = self.client.get("/blog/")
        self.assertEqual(r.status_code, 200)
        content = r.content.decode()
        # newest first post is featured, older ones in the grid
        self.assertIn("Latest story", content)
        self.assertIn("First Story", content)
        self.assertIn("Second Story", content)
        # annotated counts: 1 like, 1 approved comment (spam hidden)
        self.assertContains(r, "1 min read")
        self.assertNotContains(r, "Hidden Draft")
        ctx = r.context
        self.assertEqual(ctx["featured"].pk, self.first.pk)
        self.assertEqual([p.pk for p in ctx["posts"]], [self.second.pk])
        self.assertEqual(ctx["featured"].likes_count, 1)
        self.assertEqual(ctx["featured"].comments_count, 1)

    def test_empty_state(self):
        Post.objects.all().delete()
        r = self.client.get("/blog/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "No stories yet")

    def test_reading_time(self):
        self.assertEqual(self.second.reading_time_minutes, 1)
        self.assertGreaterEqual(self.first.reading_time_minutes, 1)
        self.assertEqual(Post(content="").reading_time_minutes, 1)
