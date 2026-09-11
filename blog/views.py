from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import CommentForm
from .models import Comment, Like, Post


def post_list(request):
    # Annotated counts (approved comments only) so the template never
    # triggers N+1 queries. Names intentionally match the model helpers —
    # annotations shadow the methods on these instances.
    qs = (
        Post.objects.filter(status=Post.STATUS_PUBLISHED)
        .select_related("author")
        .annotate(
            likes_count=Count("likes", distinct=True),
            comments_count=Count(
                "comments", filter=Q(comments__is_approved=True), distinct=True
            ),
        )
    )
    posts = list(qs)
    featured, rest = (posts[0], posts[1:]) if posts else (None, [])
    return render(
        request,
        "blog/list.html",
        {"featured": featured, "posts": rest, "total": len(posts)},
    )


def post_detail(request, slug):
    post = get_object_or_404(Post, slug=slug, status=Post.STATUS_PUBLISHED)
    comments = post.visible_comments()
    comment_form = CommentForm()
    liked = post.user_has_liked(request.user)
    related = (
        Post.objects.filter(status=Post.STATUS_PUBLISHED)
        .exclude(pk=post.pk)
        .select_related("author")[:3]
    )
    return render(
        request,
        "blog/detail.html",
        {
            "post": post,
            "comments": comments,
            "comment_form": comment_form,
            "liked": liked,
            "related": related,
        },
    )


@login_required
@require_POST
def post_comment(request, slug):
    post = get_object_or_404(Post, slug=slug, status=Post.STATUS_PUBLISHED)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.author = request.user
        comment.save()
        messages.success(request, "Comment posted.")
    else:
        messages.error(request, "Comment could not be posted.")
    return redirect("blog:detail", slug=post.slug)


@login_required
@require_POST
def comment_delete(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    post_slug = comment.post.slug
    if comment.author != request.user and not request.user.is_staff:
        messages.error(request, "You cannot delete that comment.")
    else:
        comment.delete()
        messages.success(request, "Comment deleted.")
    return redirect("blog:detail", slug=post_slug)


@login_required
@require_POST
def post_like(request, slug):
    post = get_object_or_404(Post, slug=slug, status=Post.STATUS_PUBLISHED)
    like, created = Like.objects.get_or_create(post=post, user=request.user)
    if not created:
        like.delete()
        messages.info(request, "Removed your like.")
    else:
        messages.success(request, "Liked!")
    return redirect("blog:detail", slug=post.slug)
