from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from blog.models import Comment, Like
from core.models import Review
from registrations.models import Registration

from .forms import ProfileForm, SignUpForm

User = get_user_model()


def signup(request):
    if request.user.is_authenticated:
        return redirect("accounts:profile")
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Welcome to BBCC ICT Fest 2026! Your account is ready.")
            return redirect("accounts:profile")
    else:
        form = SignUpForm()
    return render(request, "accounts/signup.html", {"form": form})


@login_required
def profile(request):
    """Dedicated dashboard page for the logged-in user."""
    user = request.user
    registrations = (
        Registration.objects.filter(user=user).prefetch_related("events").order_by("-created_at")
    )
    try:
        review = user.review
    except Review.DoesNotExist:
        review = None
    liked_posts = (
        Like.objects.filter(user=user).select_related("post").order_by("-created_at")[:10]
    )
    comments = (
        Comment.objects.filter(author=user).select_related("post").order_by("-created_at")[:10]
    )
    return render(
        request,
        "accounts/profile.html",
        {
            "registrations": registrations,
            "review": review,
            "liked_posts": liked_posts,
            "comments": comments,
        },
    )


@login_required
def profile_edit(request):
    profile = request.user.profile
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("accounts:profile")
    else:
        form = ProfileForm(instance=profile, user=request.user)
    return render(request, "accounts/profile_edit.html", {"form": form})


def public_profile(request, username):
    """Public profile page for any user."""
    profile_user = get_object_or_404(User, username=username)
    try:
        review = profile_user.review
        if not review.is_approved:
            review = None
    except Review.DoesNotExist:
        review = None
    return render(
        request,
        "accounts/public_profile.html",
        {"profile_user": profile_user, "review": review},
    )
