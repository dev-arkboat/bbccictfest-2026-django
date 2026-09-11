import itertools
import logging
import re
import uuid

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
from accounts.models import Profile, Role, role_rank
from core.forms import PersonReviewForm
from core.models import PersonReview, SiteSetting
from core.qr import qr_png_bytes
from schools.models import School

from . import bkash
from .bkash import BkashConfigError, BkashError
from .forms import MultiEventRegistrationForm, RegistrationForm
from .models import Event, PaymentTransaction, Registration

User = get_user_model()

logger = logging.getLogger("registrations.bkash")

GUEST_SESSION_KEY = "guest_registrations"


def _guest_registration_ids(request):
    """PKs of guest registrations made/located from this browser session."""
    return [
        pk for pk in request.session.get(GUEST_SESSION_KEY, []) if isinstance(pk, int)
    ]


def _remember_guest_registration(request, reg):
    ids = _guest_registration_ids(request)
    if reg.pk not in ids:
        request.session[GUEST_SESSION_KEY] = (ids + [reg.pk])[-20:]


def _can_view_registration(request, reg):
    """Owner, organizer, or same-browser guest session may view/pay a row."""
    if request.user.is_authenticated and role_rank(request.user) >= 3:
        return True
    if request.user.is_authenticated and reg.user_id == request.user.pk:
        return True
    return reg.pk in _guest_registration_ids(request)


def _registration_home(request, reg):
    """Where to send someone after a payment step: private detail page for
    logged-in owners/organizers, public receipt page for guests."""
    if request.user.is_authenticated and (
        reg.user_id == request.user.pk or role_rank(request.user) >= 3
    ):
        return redirect("registrations:detail", pk=reg.pk)
    return redirect("registrations:receipt", pk=reg.pk)


def _digits(value):
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def event_list(request):
    """Combined registration page: personal details once, tick every segment
    wanted, live total, one submit — one bKash payment for the whole bundle.
    """
    events = Event.objects.filter(is_active=True)
    site = SiteSetting.get_solo()
    preselected = {
        slug for slug in (request.GET.get("events") or "").split(",") if slug
    }
    user = request.user if request.user.is_authenticated else None
    if request.method == "POST":
        if not site.register_status:
            messages.error(request, "Registrations are currently closed.")
            return redirect("registrations:events")
        form = MultiEventRegistrationForm(request.POST)
        if form.is_valid():
            return _process_multi_registration(request, form, user)
    else:
        initial = {}
        if user is not None:
            initial = {
                "full_name": user.get_full_name() or user.username,
                "email": user.email,
                "phone": getattr(getattr(user, "profile", None), "phone", ""),
                "class_name": getattr(getattr(user, "profile", None), "class_name", ""),
            }
        form = MultiEventRegistrationForm(initial=initial or None)
    if form.is_bound:
        picked = set(form["events"].value() or [])
    else:
        picked = {str(e.pk) for e in events if e.slug in preselected}
    segments = [
        {"event": e, "checked": str(e.pk) in picked} for e in events
    ]
    return render(
        request,
        "registrations/event_list.html",
        {
            "events": events,
            "site": site,
            "form": form,
            "preselected": preselected,
            "segments": segments,
        },
    )


def _process_multi_registration(request, form, user):
    """Create one row per chosen segment (reusing unpaid rows for logged-in
    users), then confirm free bundles instantly or start one combined payment.
    """
    from django.utils import timezone

    data = form.cleaned_data
    chosen = data["events"]
    gid = uuid.uuid4().hex
    rows, skipped = [], []
    for event in chosen:
        existing = None
        if user is not None:
            existing = Registration.objects.filter(user=user, event=event).first()
            if existing is not None and existing.is_paid:
                skipped.append(event.name)
                continue
        if existing is None:
            existing = Registration(user=user)
        existing.event = event
        existing.full_name = data["full_name"]
        existing.email = data["email"]
        existing.phone = data["phone"]
        existing.school = data["school"]
        existing.institution = data["school"].name
        existing.class_name = data["class_name"]
        existing.address = data.get("address", "")
        existing.amount_bdt = event.fee_bdt
        existing.group_id = gid
        if event.is_free:
            existing.status = Registration.STATUS_CONFIRMED
            existing.confirmed_at = timezone.now()
        else:
            existing.status = Registration.STATUS_PAYMENT_PENDING
        existing.save()
        _remember_guest_registration(request, existing)
        rows.append(existing)

    if skipped:
        messages.info(
            request,
            "Already registered (not charged again): " + ", ".join(skipped) + ".",
        )
    if not rows:
        return redirect("registrations:events")
    refs = ", ".join(r.reference for r in rows)
    total = sum(r.amount_bdt for r in rows if r.status in Registration.PAYABLE_STATUSES)
    if total <= 0:
        messages.success(request, f"Registered! Your number(s): {refs}.")
        return redirect("registrations:receipt", pk=rows[0].pk)
    messages.success(request, f"Registered ({refs}). Complete the combined payment below.")
    return redirect("registrations:pay", pk=rows[0].pk)


def _payable_group_regs(reg):
    """Rows covered by one checkout: unpaid group mates, or just this row."""
    if reg.group_id:
        return list(
            Registration.objects.filter(group_id=reg.group_id)
            .exclude(status__in=[
                Registration.STATUS_PAID, Registration.STATUS_CONFIRMED,
                Registration.STATUS_CANCELLED, Registration.STATUS_REFUNDED,
            ])
            .select_related("event")
            .order_by("pk")
        )
    if reg.status in Registration.PAYABLE_STATUSES:
        return [reg]
    return []


def _group_mates(reg):
    """Every row of a checkout group (for receipts), else just this row."""
    if reg.group_id:
        return list(
            Registration.objects.filter(group_id=reg.group_id)
            .select_related("event")
            .order_by("pk")
        )
    return [reg]


def _start_group_payment(request, regs):
    """Create (or reuse) one bKash transaction for the summed group total."""
    total = sum(int(r.amount_bdt) for r in regs)
    if total <= 0:
        raise BkashError("Nothing to pay for.")
    gid = regs[0].group_id
    txn = None
    if gid:
        txn = (
            PaymentTransaction.objects.filter(group_id=gid, status="initiated", amount_bdt=total)
            .order_by("-created_at")
            .first()
        )
    else:
        txn = (
            regs[0].payments.filter(status="initiated", amount_bdt=total)
            .order_by("-created_at")
            .first()
        )
    if txn is None or not txn.bkash_url:
        first = regs[0]
        username = request.user.username if request.user.is_authenticated else ""
        payer_reference = (first.phone or first.email or username or "guest")[:40]
        invoice = (("GRP" + gid) if gid else first.reference.replace("-", ""))[:20]
        creation, raw = bkash.create_payment(
            amount_bdt=total,
            payer_reference=payer_reference,
            invoice_number=invoice,
            request=request,
        )
        txn = PaymentTransaction.objects.create(
            registration=first,
            group_id=gid,
            payment_id=creation.payment_id,
            amount_bdt=total,
            status="initiated",
            payer_reference=payer_reference,
            bkash_url=creation.bkash_url,
            raw_create=raw,
        )
        for row in regs:
            row.bkash_payment_id = creation.payment_id
            row.status = Registration.STATUS_PAYMENT_PENDING
            row.save(update_fields=["bkash_payment_id", "status", "updated_at"])
    return txn, total


def register(request, slug):
    """Register for an event — no login needed.

    Logged-in users get the row linked to their account (one row per event);
    guests get a fresh row every time (duplicates allowed) plus a session
    key so they can reach their receipt and payment pages.
    """
    event = get_object_or_404(Event, slug=slug, is_active=True)
    site = SiteSetting.get_solo()
    if not site.register_status and request.method == "POST":
        messages.error(request, "Registrations are currently closed.")
        return redirect("registrations:events")

    user = request.user if request.user.is_authenticated else None
    existing = None
    if user is not None:
        existing = Registration.objects.filter(user=user, event=event).first()
        if existing is not None and existing.is_paid:
            messages.info(request, f"You are already registered for {event.name}.")
            return redirect("registrations:detail", pk=existing.pk)

    if request.method == "POST":
        form = RegistrationForm(request.POST, instance=existing)
        if form.is_valid():
            reg = form.save(commit=False)
            if user is not None:
                reg.user = user
            reg.event = event
            reg.amount_bdt = event.fee_bdt
            if event.is_free:
                reg.status = Registration.STATUS_CONFIRMED
                from django.utils import timezone

                reg.confirmed_at = timezone.now()
                reg.save()
                _remember_guest_registration(request, reg)
                messages.success(
                    request, f"Registered for {event.name}! Your number is {reg.reference}."
                )
                return redirect("registrations:receipt", pk=reg.pk)
            reg.status = Registration.STATUS_PAYMENT_PENDING
            reg.save()
            _remember_guest_registration(request, reg)
            return redirect("registrations:pay", pk=reg.pk)
    else:
        initial = {}
        if existing is None and user is not None:
            initial = {
                "full_name": user.get_full_name() or user.username,
                "email": user.email,
                "phone": getattr(getattr(user, "profile", None), "phone", ""),
                "institution": getattr(getattr(user, "profile", None), "institution", ""),
                "class_name": getattr(getattr(user, "profile", None), "class_name", ""),
            }
        form = RegistrationForm(instance=existing, initial=initial or None)
    return render(
        request,
        "registrations/register_form.html",
        {"form": form, "event": event, "existing": existing},
    )


def pay(request, pk):
    """Start (or resume) the bKash payment — one transaction for the whole
    checkout group when several segments were registered together."""
    reg = get_object_or_404(Registration.objects.select_related("event"), pk=pk)
    if not _can_view_registration(request, reg):
        messages.error(request, "Use the registration lookup to open this payment.")
        return redirect("registrations:lookup")
    mates = _payable_group_regs(reg)
    if not mates:
        return _registration_home(request, reg)
    if mates[0].event.is_free and len(mates) == 1:
        messages.info(request, "This event is free — no payment needed.")
        return _registration_home(request, reg)

    try:
        txn, total = _start_group_payment(request, mates)
    except (BkashError, BkashConfigError) as exc:
        messages.error(request, str(exc))
        return _registration_home(request, reg)

    return render(
        request,
        "registrations/payment_redirect.html",
        {"registration": mates[0], "registrations": mates, "total": total, "txn": txn},
    )


def bkash_callback(request):
    """bKash redirects the payer here: ?paymentID=...&status=success|failure|cancel.

    The query params are only a *signal* — money is trusted only after
    server-side execute + query verification + amount match.
    """
    payment_id = (request.GET.get("paymentID") or "").strip()
    status = (request.GET.get("status") or "").strip().lower()
    if not payment_id:
        messages.error(request, "Invalid payment callback (missing payment ID).")
        return redirect("registrations:events")

    txn = PaymentTransaction.objects.select_related("registration", "registration__event").filter(
        payment_id=payment_id
    ).order_by("-created_at").first()
    if txn is None:
        messages.error(request, "Payment record not found. Contact support with your reference.")
        return redirect("registrations:events")
    reg = txn.registration
    mates = _payable_group_regs(reg)
    first = mates[0] if mates else reg

    if not mates or all(m.is_paid for m in _group_mates(reg)):
        messages.info(request, "Payment already confirmed.")
        return redirect("registrations:success", pk=first.pk)

    if status == "cancel":
        txn.status = "callback_cancel"
        txn.save(update_fields=["status", "updated_at"])
        return redirect("registrations:failed", pk=first.pk)
    if status != "success":
        txn.status = "callback_fail"
        txn.error = f"Gateway returned status={status!r}."
        txn.save(update_fields=["status", "error", "updated_at"])
        return redirect("registrations:failed", pk=first.pk)

    txn.status = "callback_success"
    txn.save(update_fields=["status", "updated_at"])

    # --- Execute server-side (this is what actually captures funds). ---
    try:
        execution, raw_execute = bkash.execute_payment(payment_id)
        if bkash.is_mock_mode():
            # Mock has no real amount — mirror the expected group total.
            execution.amount = str(sum(int(m.amount_bdt) for m in mates))
    except (BkashError, BkashConfigError) as exc:
        txn.status = "failed"
        txn.error = str(exc)
        txn.save(update_fields=["status", "error", "updated_at"])
        messages.error(request, f"Payment execution failed: {exc}")
        return redirect("registrations:failed", pk=first.pk)

    txn.raw_execute = raw_execute

    # --- Double-verify with query + amount match before trusting money. ---
    try:
        _, raw_query = bkash.query_payment(payment_id)
        txn.raw_query = raw_query
    except (BkashError, BkashConfigError) as exc:
        logger.warning("bKash query failed for %s: %s", payment_id, exc)

    try:
        if len(mates) > 1 or mates[0].group_id:
            paid = bkash.finalize_group_paid_registrations(registrations=mates, execution=execution)
        else:
            paid = [bkash.finalize_paid_registration(registration=mates[0], execution=execution)]
    except BkashError as exc:
        txn.status = "failed"
        txn.error = str(exc)
        txn.raw_execute = raw_execute
        txn.save(update_fields=["status", "error", "raw_execute", "raw_query", "updated_at"])
        messages.error(request, str(exc))
        return redirect("registrations:failed", pk=first.pk)

    txn.trx_id = paid[0].bkash_trx_id if paid else ""
    txn.status = "completed"
    txn.save(update_fields=["trx_id", "status", "raw_execute", "raw_query", "updated_at"])
    refs = ", ".join(r.reference for r in paid)
    messages.success(request, f"Payment successful! {refs} (TrxID: {txn.trx_id})")
    return redirect("registrations:success", pk=first.pk)


def payment_success(request, pk):
    reg = get_object_or_404(Registration, pk=pk)
    if not _can_view_registration(request, reg):
        messages.error(request, "Use the registration lookup to view this page.")
        return redirect("registrations:lookup")
    return render(
        request,
        "registrations/payment_success.html",
        {"registration": reg, "group_registrations": _group_mates(reg)},
    )


def payment_failed(request, pk):
    reg = get_object_or_404(Registration, pk=pk)
    if not _can_view_registration(request, reg):
        messages.error(request, "Use the registration lookup to view this page.")
        return redirect("registrations:lookup")
    latest_error = reg.payments.exclude(error="").order_by("-created_at").first()
    return render(
        request,
        "registrations/payment_failed.html",
        {
            "registration": reg,
            "latest_error": latest_error,
            "group_registrations": _group_mates(reg),
        },
    )


@login_required
def my_registrations(request):
    regs = Registration.objects.filter(user=request.user).select_related("event")
    return render(request, "registrations/my_list.html", {"registrations": regs})


@login_required
def registration_detail(request, pk):
    reg = get_object_or_404(Registration, pk=pk)
    if reg.user != request.user:
        # Layered admin: organizers+ can view any registration.
        if role_rank(request.user) < 3:
            messages.error(request, "You do not have permission to view that.")
            return redirect("registrations:my")
    return render(request, "registrations/detail.html", {"registration": reg})


def registration_receipt(request, pk):
    """Public receipt page: same details, reachable from the browser session
    that made the registration (no login needed)."""
    reg = get_object_or_404(Registration, pk=pk)
    if not _can_view_registration(request, reg):
        messages.error(
            request, "Enter your registration number and phone number to view it."
        )
        return redirect("registrations:lookup")
    return render(
        request,
        "registrations/detail.html",
        {
            "registration": reg,
            "is_guest_view": True,
            "group_registrations": _group_mates(reg),
        },
    )


def registration_lookup(request):
    """Find any registration with its number (e.g. BBCC26-00001) plus the
    phone number used at registration. Phone/email are not unique — many
    rows may share them — so the reference is the key and the phone proves
    ownership of that row."""
    if request.method == "POST":
        reference = (request.POST.get("reference") or "").replace(" ", "").upper()
        phone = _digits(request.POST.get("phone"))
        match = re.fullmatch(r"BBCC26-?0*(\d{1,5})", reference)
        reg = None
        if match and phone:
            try:
                reg = Registration.objects.select_related("event").get(pk=int(match.group(1)))
            except Registration.DoesNotExist:
                reg = None
        if reg is not None and _digits(reg.phone) == phone:
            _remember_guest_registration(request, reg)
            messages.success(request, f"Found registration {reg.reference}.")
            return render(
                request,
                "registrations/detail.html",
                {
                    "registration": reg,
                    "is_guest_view": True,
                    "group_registrations": _group_mates(reg),
                },
            )
        messages.error(
            request, "No registration found for that number and phone. Check both and try again."
        )
    return render(request, "registrations/lookup.html")


@require_POST
def refresh_status(request, pk):
    """Manually re-query bKash for a stuck payment_pending registration."""
    reg = get_object_or_404(Registration, pk=pk)
    if not _can_view_registration(request, reg):
        messages.error(request, "Use the registration lookup to open this payment.")
        return redirect("registrations:lookup")
    if reg.is_paid:
        messages.info(request, "Already paid.")
        return _registration_home(request, reg)
    if not reg.bkash_payment_id:
        messages.error(request, "No bKash payment started yet.")
        return redirect("registrations:pay", pk=reg.pk)
    if not _payable_group_regs(reg):
        messages.info(request, "Nothing left to pay on this registration.")
        return _registration_home(request, reg)
    try:
        _, raw_query = bkash.query_payment(reg.bkash_payment_id)
        txn = reg.payments.order_by("-created_at").first()
        if txn is not None:
            txn.raw_query = raw_query
            txn.save(update_fields=["raw_query", "updated_at"])
        # Try executing (safe: bKash execute is idempotent-ish; failures surface).
        execution, raw_execute = bkash.execute_payment(reg.bkash_payment_id)
        mates = _payable_group_regs(reg)
        if bkash.is_mock_mode():
            execution.amount = str(sum(int(m.amount_bdt) for m in mates))
        if len(mates) > 1 or (mates and mates[0].group_id):
            bkash.finalize_group_paid_registrations(registrations=mates, execution=execution)
        elif mates:
            bkash.finalize_paid_registration(registration=mates[0], execution=execution)
        if txn is not None:
            txn.status = "completed"
            txn.trx_id = reg.bkash_trx_id
            txn.raw_execute = raw_execute
            txn.save(update_fields=["status", "trx_id", "raw_execute", "updated_at"])
        messages.success(request, "Payment confirmed!")
        return redirect("registrations:success", pk=reg.pk)
    except (BkashError, BkashConfigError) as exc:
        messages.error(request, f"Still pending: {exc}")
        return _registration_home(request, reg)


@organizer_required
def organizer_board(request):
    regs = Registration.objects.select_related("event", "user").order_by("-created_at")[:200]
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

    regs = Registration.objects.select_related("event", "school", "user").order_by("-created_at")
    if q:
        class_q = re.sub(r"(?i)^class\s+", "", q)
        lookups = (
            Q(full_name__icontains=q)
            | Q(email__icontains=q)
            | Q(school__name__icontains=q)
            | Q(institution__icontains=q)
            | Q(class_name__icontains=class_q)
            | Q(serial_number__icontains=q)
        )
        digits = _digits(q)
        if digits:
            lookups |= Q(phone__contains=digits)
        ref = q.replace(" ", "").upper()
        match = re.fullmatch(r"BBCC26-?0*(\d{1,5})", ref)
        if match:
            lookups |= Q(pk=int(match.group(1)))
        elif ref.lstrip("0").isdigit():
            lookups |= Q(pk=int(ref.lstrip("0")))
        regs = regs.filter(lookups)
    if event_id.isdigit():
        regs = regs.filter(event_id=int(event_id))
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
        .select_related("event")
        .order_by("-created_at")
    )
    if q:
        lookups = (
            Q(full_name__icontains=q)
            | Q(email__icontains=q)
            | Q(class_name__icontains=q)
            | Q(serial_number__icontains=q)
        )
        digits = _digits(q)
        if digits:
            lookups |= Q(phone__contains=digits)
        ref = q.replace(" ", "").upper()
        match = re.fullmatch(r"BBCC26-?0*(\d{1,5})", ref)
        if match:
            lookups |= Q(pk=int(match.group(1)))
        participants = participants.filter(lookups)
    if event_id.isdigit():
        participants = participants.filter(event_id=int(event_id))
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
