from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from blog.models import Post
from registrations.models import Event
from volunteers.models import Volunteer

from .forms import ReviewForm
from .models import (
    CommitteeCategory,
    Competition,
    FAQ,
    Game,
    Guest,
    HeroChip,
    Review,
    SiteSetting,
    Sponsor,
    Stat,
    TickerItem,
    TimelineStep,
)


def _home_context():
    site = SiteSetting.get_solo()
    reviews = (
        Review.objects.filter(is_approved=True)
        .select_related("user", "user__profile")
        .order_by("-updated_at")[:12]
    )
    rating_stats = Review.objects.filter(is_approved=True).aggregate(
        avg=Avg("rating"), count=Count("id")
    )
    sponsors = list(Sponsor.objects.filter(is_active=True))
    return {
        "site": site,
        "chips": HeroChip.objects.filter(is_active=True),
        "ticker_items": TickerItem.objects.filter(is_active=True),
        "stats": Stat.objects.all(),
        "competitions": Competition.objects.filter(is_active=True).prefetch_related(
            "tags", "details"
        ),
        "timeline": TimelineStep.objects.all(),
        "guests": Guest.objects.filter(is_active=True),
        "committee_categories": CommitteeCategory.objects.prefetch_related("members").all(),
        "sponsors": sponsors,
        # The marquee translates -50% across two identical halves, so each
        # half repeats the sequence 3x (like the original design) to keep
        # the loop seamless even with only a few sponsors on file.
        "sponsors_track": sponsors * 3,
        "faqs": FAQ.objects.filter(is_active=True),
        "events": Event.objects.filter(is_active=True),
        "reviews": reviews,
        "rating_avg": round(rating_stats["avg"] or 0, 1),
        "rating_count": rating_stats["count"] or 0,
        "volunteers_preview": Volunteer.objects.filter(is_active=True)[:8],
        "latest_posts": Post.objects.filter(status=Post.STATUS_PUBLISHED).select_related(
            "author"
        )[:3],
    }


def home(request):
    return render(request, "core/home.html", _home_context())


def arcade_index(request):
    games = Game.objects.filter(is_active=True)
    return render(request, "arcade/index.html", {"games": games})


def game_play(request, slug):
    game = get_object_or_404(Game, slug=slug, is_active=True)
    games = Game.objects.filter(is_active=True)
    return render(
        request, f"arcade/{game.slug}.html", {"game": game, "games": games}
    )


def reviews_list(request):
    reviews = (
        Review.objects.filter(is_approved=True)
        .select_related("user", "user__profile")
        .order_by("-updated_at")
    )
    stats = Review.objects.filter(is_approved=True).aggregate(
        avg=Avg("rating"), count=Count("id")
    )
    my_review = None
    if request.user.is_authenticated:
        my_review = getattr(request.user, "review", None)
    return render(
        request,
        "core/reviews.html",
        {
            "reviews": reviews,
            "rating_avg": round(stats["avg"] or 0, 1),
            "rating_count": stats["count"] or 0,
            "my_review": my_review,
        },
    )


@login_required
def review_upsert(request):
    """Create or edit the single review of the logged-in user."""
    review = getattr(request.user, "review", None)
    if request.method == "POST":
        form = ReviewForm(request.POST, instance=review)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.user = request.user
            obj.is_approved = True
            obj.save()
            messages.success(request, "Thanks! Your review has been saved.")
            return redirect("core:reviews")
    else:
        form = ReviewForm(instance=review)
    return render(request, "core/review_form.html", {"form": form, "review": review})


@login_required
@require_POST
def review_delete(request):
    review = getattr(request.user, "review", None)
    if review is not None:
        review.delete()
        messages.success(request, "Your review was deleted.")
    return redirect("core:reviews")


def robots_txt(request):
    from django.conf import settings

    base = getattr(settings, "SITE_URL", "https://bbccictfest.pro.bd").rstrip("/")
    content = f"User-agent: *\nAllow: /\n\nSitemap: {base}/sitemap.xml\n"
    return HttpResponse(content, content_type="text/plain")
