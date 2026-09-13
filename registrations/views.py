import itertools
import re

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.decorators import organizer_required, volunteer_required
from accounts.forms import CampusAmbassadorCreateForm
from accounts.models import Profile, Role
from core.forms import PersonReviewForm
from core.models import PersonReview
from core.qr import qr_png_bytes
from schools.models import School

from .models import Event, Registration

User = get_user_model()


def _digits(value):
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def event_list(request):
    """Offline-only registration info page.

    Participant signups happen on paper at the venue / through organizers
    and are entered from the admin panel. This page just says so and lists
    the segments with their fees for reference.
    """
    events = Event.objects.filter(is_active=True)
    return render(request, "registrations/event_list.html", {"events": events})


@organizer_required
def organizer_board(request):
    regs = (
        Registration.objects.select_related("school", "user")
        .prefetch_related("events")
        .order_by("-created_at")[:200]
    )
    return render(request, "registrations/board.html", {"registrations": regs})


@volunteer_required
def verify_registrations(request):
    """Fest-day gate tool: find any registration by phone, reference number,
    serial number, name, school, email or class — then filter and check in."""
    from django.core.paginator import Paginator

    q = (request.GET.get("q") or "").strip()
    event_id = request.GET.get("event") or ""
    status = request.GET.get("status") or ""
    school_id = request.GET.get("school") or ""
    checked = request.GET.get("checked_in") or ""

    regs = (
        Registration.objects.select_related("school", "user")
        .prefetch_related("events")
        .order_by("-created_at")
    )
    if q:
        class_q = re.sub(r"(?i)^class\s+", "", q)
        lookups = (
            Q(full_name__icontains=q)
            | Q(email__icontains=q)
            | Q(school__name__icontains=q)
            | Q(class_name__icontains=class_q)
            | Q(events__name__icontains=q)
        )
        digits = _digits(q)
        if digits:
            lookups |= Q(phone__contains=digits)
            # serial_number is an integer — exact match on its digits.
            if digits.isdigit():
                lookups |= Q(serial_number=int(digits))
        ref = q.replace(" ", "").upper()
        match = re.fullmatch(r"BBCC26-?0*(\d{1,5})", ref)
        if match:
            lookups |= Q(pk=int(match.group(1)))
        elif ref.lstrip("0").isdigit():
            lookups |= Q(pk=int(ref.lstrip("0")))
        regs = regs.filter(lookups).distinct()
    if event_id.isdigit():
        regs = regs.filter(events__id=int(event_id))
    if status in dict(Registration.STATUS_CHOICES):
        regs = regs.filter(status=status)
    if school_id.isdigit():
        regs = regs.filter(school_id=int(school_id))
    if checked == "1":
        regs = regs.filter(checked_in=True)
    elif checked == "0":
        regs = regs.filter(checked_in=False)

    page_obj = Paginator(regs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "registrations/verify.html",
        {
            "page": page_obj,
            "total": page_obj.paginator.count,
            "q": q,
            "events": Event.objects.filter(is_active=True),
            "statuses": Registration.STATUS_CHOICES,
            "schools": School.objects.filter(is_active=True),
            "f": {"event": event_id, "status": status, "school": school_id, "checked_in": checked},
        },
    )


@volunteer_required
@require_POST
def check_in_toggle(request, pk):
    """Tick/untick fest-day entry for one registration."""
    reg = get_object_or_404(Registration, pk=pk)
    reg.checked_in = not reg.checked_in
    if reg.checked_in:
        from django.utils import timezone

        reg.checked_in_at = timezone.now()
    else:
        reg.checked_in_at = None
    reg.save(update_fields=["checked_in", "checked_in_at", "updated_at"])
    messages.success(
        request,
        f"{reg.reference} ({reg.full_name}) "
        + ("checked in." if reg.checked_in else "check-in removed."),
    )
    goto = request.POST.get("next", "")
    if goto.startswith("/"):
        return redirect(goto)
    return redirect("registrations:verify")


def _ca_display_name(user):
    """Full name or username — ambassadors are plain users, no separate row."""
    return user.get_full_name() or user.username


def _ca_school(user):
    profile = getattr(user, "profile", None)
    return getattr(profile, "school", None)


def ambassador_list(request):
    """Public Campus Ambassador section — users with the Campus Ambassador role.

    Grouped by school (CAs without a school last) with per-card ratings.
    """
    ambassadors = (
        User.objects.filter(profile__role=Role.CAMPUS_AMBASSADOR)
        .select_related("profile__school")
        .annotate(
            avg_rating=Avg(
                "received_reviews__rating",
                filter=Q(received_reviews__is_approved=True),
            ),
            rating_count=Count(
                "received_reviews",
                filter=Q(received_reviews__is_approved=True),
            ),
        )
        .order_by("profile__school__order", "profile__school__name", "username")
    )
    groups = []
    for _school_id, members in itertools.groupby(ambassadors, key=lambda a: _ca_school(a)):
        members = list(members)
        groups.append((_ca_school(members[0]), members))
    groups.sort(key=lambda group: group[0] is None)
    school_count = sum(1 for school, _members in groups if school is not None)
    return render(
        request,
        "registrations/ca_list.html",
        {
            "ambassadors": ambassadors,
            "groups": groups,
            "ambassador_count": len(ambassadors),
            "school_count": school_count,
        },
    )


def ambassador_detail(request, pk):
    """Public profile page for one ambassador — no login needed."""
    ambassador = _approved_ambassador_or_404(pk)
    reviews = (
        PersonReview.objects.filter(ambassador_user=ambassador, is_approved=True)
        .select_related("user", "user__profile")
        .order_by("-updated_at")
    )
    stats = reviews.aggregate(avg=Avg("rating"), count=Count("id"))
    my_review = None
    if request.user.is_authenticated:
        my_review = PersonReview.objects.filter(
            user=request.user, ambassador_user=ambassador
        ).first()
    return render(
        request,
        "registrations/ca_detail.html",
        {
            "ambassador": ambassador,
            "ambassador_name": _ca_display_name(ambassador),
            "school": _ca_school(ambassador),
            "reviews": reviews,
            "rating_avg": round(stats["avg"] or 0, 1),
            "rating_count": stats["count"] or 0,
            "my_review": my_review,
            "review_form": PersonReviewForm(instance=my_review),
        },
    )


@login_required
@require_POST
def ambassador_review_upsert(request, pk):
    """Create or edit the logged-in user's rating for one ambassador."""
    ambassador = _approved_ambassador_or_404(pk)
    review = PersonReview.objects.filter(
        user=request.user, ambassador_user=ambassador
    ).first()
    form = PersonReviewForm(request.POST, instance=review)
    if form.is_valid():
        obj = form.save(commit=False)
        obj.user = request.user
        obj.ambassador_user = ambassador
        obj.volunteer = None
        obj.is_approved = True
        obj.save()
        messages.success(request, "Thanks! Your rating has been saved.")
    else:
        messages.error(request, "Could not save your rating — check the form.")
    return redirect("registrations:ca_detail", pk=ambassador.pk)


@login_required
@require_POST
def ambassador_review_delete(request, pk):
    ambassador = _approved_ambassador_or_404(pk)
    review = PersonReview.objects.filter(
        user=request.user, ambassador_user=ambassador
    ).first()
    if review is not None:
        review.delete()
        messages.success(request, "Your rating was deleted.")
    return redirect("registrations:ca_detail", pk=ambassador.pk)


def _approved_ambassador_or_404(pk):
    """A user holding the Campus Ambassador role — the only kind that is public."""
    return get_object_or_404(User, pk=pk, profile__role=Role.CAMPUS_AMBASSADOR)


def ambassador_qr(request, pk):
    """QR code PNG pointing at this ambassador's public page (public)."""
    ambassador = _approved_ambassador_or_404(pk)
    png = qr_png_bytes(
        request.build_absolute_uri(
            reverse("registrations:ca_detail", kwargs={"pk": ambassador.pk})
        )
    )
    return HttpResponse(png, content_type="image/png")


def ambassador_qr_download(request, pk):
    """Same QR as a download — works logged in or not."""
    ambassador = _approved_ambassador_or_404(pk)
    png = qr_png_bytes(
        request.build_absolute_uri(
            reverse("registrations:ca_detail", kwargs={"pk": ambassador.pk})
        )
    )
    response = HttpResponse(png, content_type="image/png")
    response["Content-Disposition"] = (
        f'attachment; filename="ambassador-{ambassador.pk}-qr.png"'
    )
    return response


@organizer_required
def ca_create(request):
    """Organizer-only page to create a Campus Ambassador account.

    Creates the user (with a properly hashed password) plus profile in one
    go: role set to Campus Ambassador, school assigned, institution mirrored
    from the school. No public application flow exists by design.
    """
    if request.method == "POST":
        form = CampusAmbassadorCreateForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            user = User(
                username=data["username"],
                email=data.get("email", ""),
                first_name=data.get("first_name", ""),
                last_name=data.get("last_name", ""),
            )
            user.set_password(data["password1"])
            user.save()
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.role = Role.CAMPUS_AMBASSADOR
            profile.school = data["school"]
            profile.institution = data["school"].name
            profile.phone = data.get("phone", "")
            profile.bio = data.get("bio", "")
            profile.save()
            messages.success(
                request,
                f"Campus Ambassador “{user.username}” created for "
                f"{data['school'].name} — they can now log in.",
            )
            return redirect("registrations:ca_detail", pk=user.pk)
    else:
        form = CampusAmbassadorCreateForm()
    return render(request, "registrations/ca_create.html", {"form": form})


@login_required
def ca_dashboard(request):
    """A Campus Ambassador's view of their own school: its volunteers and
    its participants. Admins create ambassadors directly (role + school on
    the profile) — there is no application flow."""
    profile = getattr(request.user, "profile", None)
    if profile is None or profile.role != Role.CAMPUS_AMBASSADOR:
        messages.error(request, "Only Campus Ambassadors can access the dashboard.")
        return redirect("accounts:profile")
    school = profile.school
    if school is None:
        messages.error(
            request, "Your profile has no school assigned yet. Please contact the organizers."
        )
        return redirect("accounts:profile")
    volunteers = (
        school.volunteers.filter(is_active=True)
        .select_related("school")
        .order_by("order", "name")
    )
    q = (request.GET.get("q") or "").strip()
    event_id = request.GET.get("event") or ""
    if q:
        lookups = (
            Q(name__icontains=q)
            | Q(role__icontains=q)
        )
        digits = _digits(q)
        if digits:
            lookups |= Q(phone__contains=digits)
        volunteers = volunteers.filter(lookups)
    participants = (
        Registration.objects.filter(school=school)
        .prefetch_related("events")
        .order_by("-created_at")
    )
    if q:
        lookups = (
            Q(full_name__icontains=q)
            | Q(email__icontains=q)
            | Q(class_name__icontains=q)
            | Q(events__name__icontains=q)
        )
        digits = _digits(q)
        if digits:
            lookups |= Q(phone__contains=digits)
            if digits.isdigit():
                lookups |= Q(serial_number=int(digits))
        ref = q.replace(" ", "").upper()
        match = re.fullmatch(r"BBCC26-?0*(\d{1,5})", ref)
        if match:
            lookups |= Q(pk=int(match.group(1)))
        participants = participants.filter(lookups).distinct()
    if event_id.isdigit():
        participants = participants.filter(events__id=int(event_id))
    return render(
        request,
        "registrations/ca_dashboard.html",
        {
            "ambassador": request.user,
            "ambassador_name": _ca_display_name(request.user),
            "school": school,
            "volunteers": volunteers,
            "participants": participants,
            "q": q,
            "events": Event.objects.filter(is_active=True),
            "event_id": event_id,
        },
    )
