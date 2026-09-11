from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.forms import PersonReviewForm
from core.models import PersonReview
from core.qr import qr_png_bytes

from .models import Volunteer


def volunteer_list(request):
    volunteers = Volunteer.objects.filter(is_active=True).select_related("school")
    return render(request, "volunteers/list.html", {"volunteers": volunteers})


def volunteer_detail(request, pk):
    """Public profile page for one volunteer — no login needed."""
    volunteer = get_object_or_404(Volunteer, pk=pk, is_active=True)
    teammates = (
        Volunteer.objects.filter(is_active=True, school=volunteer.school)
        .exclude(pk=volunteer.pk)
        .select_related("school")[:8]
        if volunteer.school_id
        else []
    )
    reviews = (
        PersonReview.objects.filter(volunteer=volunteer, is_approved=True)
        .select_related("user", "user__profile")
        .order_by("-updated_at")
    )
    stats = reviews.aggregate(avg=Avg("rating"), count=Count("id"))
    my_review = None
    if request.user.is_authenticated:
        my_review = PersonReview.objects.filter(
            user=request.user, volunteer=volunteer
        ).first()
    return render(
        request,
        "volunteers/detail.html",
        {
            "volunteer": volunteer,
            "teammates": teammates,
            "reviews": reviews,
            "rating_avg": round(stats["avg"] or 0, 1),
            "rating_count": stats["count"] or 0,
            "my_review": my_review,
            "review_form": PersonReviewForm(instance=my_review),
        },
    )


@login_required
@require_POST
def volunteer_review_upsert(request, pk):
    """Create or edit the logged-in user's rating for one volunteer."""
    volunteer = get_object_or_404(Volunteer, pk=pk, is_active=True)
    review = PersonReview.objects.filter(user=request.user, volunteer=volunteer).first()
    form = PersonReviewForm(request.POST, instance=review)
    if form.is_valid():
        obj = form.save(commit=False)
        obj.user = request.user
        obj.volunteer = volunteer
        obj.ambassador = None
        obj.is_approved = True
        obj.save()
        messages.success(request, "Thanks! Your rating has been saved.")
    else:
        messages.error(request, "Could not save your rating — check the form.")
    return redirect(volunteer.get_absolute_url())


@login_required
@require_POST
def volunteer_review_delete(request, pk):
    volunteer = get_object_or_404(Volunteer, pk=pk, is_active=True)
    review = PersonReview.objects.filter(user=request.user, volunteer=volunteer).first()
    if review is not None:
        review.delete()
        messages.success(request, "Your rating was deleted.")
    return redirect(volunteer.get_absolute_url())


def volunteer_qr(request, pk):
    """QR code PNG pointing at this volunteer's public page (public)."""
    volunteer = get_object_or_404(Volunteer, pk=pk, is_active=True)
    png = qr_png_bytes(request.build_absolute_uri(volunteer.get_absolute_url()))
    return HttpResponse(png, content_type="image/png")


def volunteer_qr_download(request, pk):
    """Same QR as a download — works logged in or not."""
    volunteer = get_object_or_404(Volunteer, pk=pk, is_active=True)
    png = qr_png_bytes(request.build_absolute_uri(volunteer.get_absolute_url()))
    response = HttpResponse(png, content_type="image/png")
    response["Content-Disposition"] = (
        f'attachment; filename="volunteer-{volunteer.pk}-qr.png"'
    )
    return response
