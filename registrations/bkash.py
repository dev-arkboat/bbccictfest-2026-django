"""bKash payment service built on pybkash.

Follows the official flow (create -> redirect bkash_url -> callback
``?paymentID=...&status=...`` -> execute -> query-verify):

* https://github.com/Itsmmdoha/pybkash
* https://pypi.org/project/pybkash/
* https://dev.to/itsmmdoha/how-to-integrate-bkash-payment-gateway-in-python-the-easy-way-1997

Design notes (why this is robust):
- Credentials come from ``.env`` via ``python-dotenv`` (never hardcoded).
- Every gateway step is persisted on ``PaymentTransaction`` with raw
  payloads, so payments are auditable / retryable / reconcilable.
- ``execute`` is always followed by ``query`` verification and an amount
  check before money is trusted — callback query params alone are NEVER
  trusted (per the security warning in the tutorial).
- Idempotent: re-hitting a callback for an already-completed payment is a
  no-op that just re-verifies.
- ``BKASH_MOCK=true`` (auto when creds are missing) runs the full flow
  locally without touching bKash — mock URLs point back at our callback.
"""

import logging
import uuid

from django.conf import settings
from django.urls import reverse

logger = logging.getLogger("registrations.bkash")


class BkashConfigError(Exception):
    """Raised when bKash is not configured and mock mode is off."""


class BkashError(Exception):
    """Raised for any gateway failure (network, API error, mismatch)."""


def is_mock_mode() -> bool:
    return bool(getattr(settings, "BKASH_MOCK", False))


def is_configured() -> bool:
    return bool(getattr(settings, "BKASH_ENABLED", False))


def _require_real():
    if not is_configured():
        raise BkashConfigError(
            "bKash credentials are missing. Fill BKASH_* in .env "
            "or keep BKASH_MOCK=True for local testing."
        )


def get_client():
    """Build a live pybkash Client from env credentials."""
    _require_real()
    from pybkash import Client, Token

    token = Token(
        username=settings.BKASH_USERNAME,
        password=settings.BKASH_PASSWORD,
        app_key=settings.BKASH_APP_KEY,
        app_secret=settings.BKASH_APP_SECRET,
        sandbox=bool(getattr(settings, "BKASH_SANDBOX", True)),
    )
    return Client(token)


def callback_url_for(request=None) -> str:
    """Absolute callback URL bKash redirects the payer back to."""
    base = (getattr(settings, "BKASH_CALLBACK_BASE", "") or "").rstrip("/") or None
    path = reverse("registrations:bkash_callback")
    if request is not None:
        return request.build_absolute_uri(path)
    if base:
        return f"{base}{path}"
    return path


def _obj_to_dict(obj) -> dict:
    try:
        data = dict(vars(obj))
        return {k: v for k, v in data.items() if not k.startswith("_")}
    except Exception:
        return {"repr": repr(obj)}


def _is_completed(execution) -> bool:
    """Defensive completion check across pybkash versions."""
    for attr in ("is_complete",):
        check = getattr(execution, attr, None)
        if callable(check):
            try:
                if check():
                    return True
            except Exception:
                pass
    status = (
        getattr(execution, "transaction_status", "")
        or getattr(execution, "status", "")
        or ""
    )
    return str(status).strip().lower() == "completed"


class MockPaymentCreation:
    def __init__(self, payment_id, bkash_url, callback_url):
        self.status_code = "0000"
        self.status_message = "Mock success"
        self.payment_id = payment_id
        self.bkash_url = bkash_url
        self.callback_url = callback_url
        self.success_callback = callback_url
        self.failure_callback = callback_url
        self.cancel_callback = callback_url


class MockPaymentExecution:
    def __init__(self, payment_id, amount):
        self.status_code = "0000"
        self.status_message = "Mock success"
        self.payment_id = payment_id
        self.trx_id = f"MOCKTRX{uuid.uuid4().hex[:10].upper()}"
        self.amount = str(amount)
        self.transaction_status = "Completed"
        self.status = "Completed"
        self.customer_msisdn = "01XXXXXXXXX"
        self.payment_execute_time = ""
        self.currency = "BDT"
        self.intent = "sale"
        self.merchant_invoice_number = payment_id

    def is_complete(self):
        return True


def create_payment(*, amount_bdt: int, payer_reference: str, invoice_number: str,
                   request=None):
    """Create a bKash payment intent. Returns (creation, raw_dict)."""
    amount = int(amount_bdt)
    if amount <= 0:
        raise BkashError("Payment amount must be positive.")
    callback_url = callback_url_for(request)

    if is_mock_mode():
        payment_id = f"MOCK-{uuid.uuid4().hex[:12].upper()}"
        sep = "&" if "?" in callback_url else "?"
        mock_url = f"{callback_url}{sep}paymentID={payment_id}&status=success&signature=mock"
        creation = MockPaymentCreation(payment_id, mock_url, callback_url)
        logger.info("bKash MOCK create: %s amount=%s", payment_id, amount)
        return creation, {"mock": True, "payment_id": payment_id, "amount": amount}

    client = get_client()
    try:
        creation = client.create_payment(
            callback_url=callback_url,
            payer_reference=str(payer_reference)[:40],
            amount=amount,
            invoice_number=str(invoice_number)[:20],
        )
    except Exception as exc:
        logger.exception("bKash create_payment failed")
        raise BkashError(f"Could not start bKash payment: {exc}") from exc
    finally:
        try:
            client.close()
        except Exception:
            pass
    if not getattr(creation, "bkash_url", None) or not getattr(creation, "payment_id", None):
        raise BkashError("bKash returned an invalid payment response.")
    logger.info("bKash create: %s amount=%s", creation.payment_id, amount)
    return creation, _obj_to_dict(creation)


def execute_payment(payment_id: str):
    """Execute an authorized payment. Returns (execution, raw_dict)."""
    if is_mock_mode():
        return MockPaymentExecution(payment_id, 0), {"mock": True, "payment_id": payment_id}

    client = get_client()
    try:
        execution = client.execute_payment(payment_id)
    except Exception as exc:
        logger.exception("bKash execute_payment failed for %s", payment_id)
        raise BkashError(f"bKash execution failed: {exc}") from exc
    finally:
        try:
            client.close()
        except Exception:
            pass
    return execution, _obj_to_dict(execution)


def query_payment(payment_id: str):
    """Query authoritative payment state. Returns (payment, raw_dict)."""
    if is_mock_mode():
        return None, {"mock": True, "payment_id": payment_id}

    client = get_client()
    try:
        payment = client.query_payment(payment_id)
    except Exception as exc:
        logger.exception("bKash query_payment failed for %s", payment_id)
        raise BkashError(f"bKash status check failed: {exc}") from exc
    finally:
        try:
            client.close()
        except Exception:
            pass
    return payment, _obj_to_dict(payment)


def finalize_paid_registration(*, registration, execution, query_raw=None):
    """Mark a registration paid after verifying execution + amount.

    Raises BkashError on any mismatch — caller decides UX.
    """
    from django.utils import timezone

    from registrations.models import Registration as Reg

    if not _is_completed(execution):
        raise BkashError(
            f"Payment not completed (status={getattr(execution, 'transaction_status', '?')})."
        )
    try:
        paid_amount = int(float(getattr(execution, "amount", 0) or 0))
    except (TypeError, ValueError):
        paid_amount = 0
    if paid_amount != int(registration.amount_bdt):
        raise BkashError(
            f"Paid amount mismatch: expected {registration.amount_bdt} BDT, "
            f"gateway says {paid_amount} BDT. Flagged for manual review."
        )

    registration.status = Reg.STATUS_PAID
    registration.bkash_trx_id = getattr(execution, "trx_id", "") or ""
    registration.bkash_customer_msisdn = getattr(execution, "customer_msisdn", "") or ""
    registration.paid_at = timezone.now()
    registration.save(
        update_fields=["status", "bkash_trx_id", "bkash_customer_msisdn", "paid_at", "updated_at"]
    )
    logger.info(
        "Registration %s marked PAID (trx=%s amount=%s)",
        registration.reference, registration.bkash_trx_id, paid_amount,
    )
    return registration


def finalize_group_paid_registrations(*, registrations, execution):
    """Mark a whole multi-segment checkout group paid from one execution.

    Verifies the gateway amount equals the SUM of the rows first — same
    trust-nothing rule as the single-row flow, applied to the group total.
    Only rows still awaiting payment are touched; already-paid rows in the
    group are left alone. Returns the list of newly-paid registrations.
    """
    from django.utils import timezone

    from registrations.models import Registration as Reg

    regs = [r for r in registrations if r.status in Reg.PAYABLE_STATUSES]
    if not _is_completed(execution):
        raise BkashError(
            f"Payment not completed (status={getattr(execution, 'transaction_status', '?')})."
        )
    try:
        paid_amount = int(float(getattr(execution, "amount", 0) or 0))
    except (TypeError, ValueError):
        paid_amount = 0
    expected = sum(int(r.amount_bdt) for r in regs)
    if paid_amount != expected:
        raise BkashError(
            f"Paid amount mismatch: expected {expected} BDT for "
            f"{len(regs)} registration(s), gateway says {paid_amount} BDT. "
            "Flagged for manual review."
        )
    trx_id = getattr(execution, "trx_id", "") or ""
    msisdn = getattr(execution, "customer_msisdn", "") or ""
    now = timezone.now()
    for reg in regs:
        reg.status = Reg.STATUS_PAID
        reg.bkash_trx_id = trx_id
        reg.bkash_customer_msisdn = msisdn
        reg.paid_at = now
        reg.save(
            update_fields=["status", "bkash_trx_id", "bkash_customer_msisdn", "paid_at", "updated_at"]
        )
    logger.info(
        "Group [%s] marked PAID (%d rows, trx=%s amount=%s)",
        getattr(regs[0], "group_id", "") if regs else "",
        len(regs), trx_id, paid_amount,
    )
    return regs
