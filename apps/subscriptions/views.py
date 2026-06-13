# apps/subscriptions/views.py
"""
Subscription payment endpoints (PhonePe v2).

Endpoints
─────────
GET  /api/subscriptions/plans/          — list plan prices (public)
POST /api/subscriptions/initiate/       — start a payment (auth required)
GET  /api/subscriptions/callback/       — PhonePe redirect after payment
POST /api/subscriptions/webhook/        — PhonePe server-to-server callback
GET  /api/subscriptions/my/             — current user's active subscription

Flow
────
  Mobile → POST /initiate/ → [PhonePe checkout] → GET /callback/
                                                 → POST /webhook/ (reliable)

The webhook is the canonical success path. The callback updates state too,
but PhonePe may retry the webhook even if callback succeeds — both are
idempotent so double-processing is safe.
"""
import json, uuid
from datetime import datetime, timedelta

from django.views.decorators.csrf import csrf_exempt

from django.http import JsonResponse

from apps.accounts.decorators import require_auth
from apps.master.models import SubscriptionPlanSettings
from apps.users.models import ClientProfile
from .models import Subscription


def api_response(success, message, data=None, status=200):
    return JsonResponse({"success": success, "message": message, "data": data}, status=status)


# ── helpers ───────────────────────────────────────────────────────────────────

_PAYABLE_PLANS = {"GOLD", "PLATINUM", "DIAMOND"}
_BILLING_CYCLES = {"monthly", "yearly"}
_CYCLE_DAYS = {"monthly": 30, "yearly": 365}


def _ser_plan(p) -> dict:
    return {
        "id":              str(p.id),
        "name":            p.name,
        "monthlyPrice":    p.monthlyPrice,
        "yearlyPrice":     p.yearlyPrice,
        "prioritySupport": p.prioritySupport,
        "isFree":          p.isFree,
    }


def _complete_subscription(subscription: Subscription, amount_rupees: float) -> None:
    """
    Mark subscription COMPLETED, set dates, and update ClientProfile plan.
    Idempotent — safe to call multiple times.
    """
    if subscription.payment_status == "COMPLETED":
        return   # already done

    now = datetime.utcnow()
    days = _CYCLE_DAYS.get(subscription.billing_cycle, 30)

    subscription.payment_status = "COMPLETED"
    subscription.amount         = amount_rupees or subscription.amount
    subscription.start_date     = now
    subscription.end_date       = now + timedelta(days=days)
    subscription.save()

    # Upgrade the client's plan on their profile
    try:
        cp = ClientProfile.objects(id=subscription.client_profile_id).first()
        if cp:
            cp.subscription_plan = subscription.plan
            cp.save()
    except Exception:
        pass   # profile update failure shouldn't break the payment record


# ── 1. List Plans ─────────────────────────────────────────────────────────────

@csrf_exempt
def list_plans(request):
    """
    GET /api/subscriptions/plans/
    Returns all subscription plans with monthly + yearly prices.
    No auth required — mobile displays these before login.
    """
    if request.method != "GET":
        return api_response(False, "Method not allowed", status=405)
    try:
        plans = SubscriptionPlanSettings.objects().order_by("name")
        return api_response(True, "Plans fetched", [_ser_plan(p) for p in plans])
    except Exception as e:
        return api_response(False, str(e), status=500)


# ── 2. Initiate Payment ───────────────────────────────────────────────────────

@csrf_exempt
@require_auth
def initiate(request):
    """
    POST /api/subscriptions/initiate/
    Body:
      {
        "plan":          "GOLD" | "PLATINUM" | "DIAMOND",
        "billing_cycle": "monthly" | "yearly",
        "redirect_url":  "nuvoapp://subscription/result"
      }

    Returns:
      {
        "redirect_url":      "<PhonePe checkout URL>",
        "merchant_order_id": "SUB-XXXX"
      }
    """
    if request.method != "POST":
        return api_response(False, "Method not allowed", status=405)
    try:
        from apps.common.phonepay_utils import initiate_payment as phonepe_initiate

        body          = json.loads(request.body)
        plan          = body.get("plan", "").strip().upper()
        billing_cycle = body.get("billing_cycle", "").strip().lower()
        redirect_url  = body.get("redirect_url", "").strip()

        # ── Validation ─────────────────────────────────────────
        if plan not in _PAYABLE_PLANS:
            return api_response(False, f"plan must be one of {_PAYABLE_PLANS}", status=400)
        if billing_cycle not in _BILLING_CYCLES:
            return api_response(False, "billing_cycle must be 'monthly' or 'yearly'", status=400)
        if not redirect_url:
            return api_response(False, "redirect_url is required", status=400)

        # ── Caller identity ────────────────────────────────────
        user_id = str(request.user.id)
        cp = ClientProfile.objects(user=user_id).first()
        if not cp:
            return api_response(False, "Client profile not found", status=404)

        # ── Plan price ─────────────────────────────────────────
        plan_settings = SubscriptionPlanSettings.objects(name=plan).first()
        if not plan_settings:
            return api_response(False, f"Plan '{plan}' not configured in master data", status=404)

        amount = plan_settings.yearlyPrice if billing_cycle == "yearly" else plan_settings.monthlyPrice
        if not amount or amount <= 0:
            return api_response(False, f"Price for {plan}/{billing_cycle} is not set", status=400)

        # ── Create pending Subscription record ─────────────────
        merchant_order_id = f"SUB-{uuid.uuid4().hex[:14].upper()}"

        sub = Subscription(
            user_id           = user_id,
            client_profile_id = str(cp.id),
            plan              = plan,
            billing_cycle     = billing_cycle,
            amount            = amount,
            merchant_order_id = merchant_order_id,
            payment_status    = "PENDING",
        )
        sub.save()

        # ── Initiate PhonePe checkout ──────────────────────────
        user_mobile = None
        try:
            from apps.users.models import User
            u = User.objects(id=user_id).first()
            if u and u.phone_number:
                user_mobile = u.phone_number
        except Exception:
            pass

        result = phonepe_initiate(
            amount_rupees     = amount,
            merchant_order_id = merchant_order_id,
            redirect_url      = redirect_url,
            user_mobile       = user_mobile,
        )

        if result.get("success"):
            sub.phonepe_order_id = result.get("phonepe_order_id", "")
            sub.save()
            return api_response(True, "Payment initiated", {
                "redirect_url":      result["redirect_url"],
                "merchant_order_id": merchant_order_id,
            })
        else:
            sub.payment_status = "FAILED"
            sub.save()
            return api_response(False, result.get("message", "Failed to initiate payment"), status=502)

    except Exception as e:
        return api_response(False, str(e), status=500)


# ── 3. Callback (browser redirect) ────────────────────────────────────────────

@csrf_exempt
def callback(request):
    """
    GET /api/subscriptions/callback/?merchantOrderId=SUB-XXXX
    PhonePe redirects the user's browser/WebView here after payment.
    The mobile app should listen for this deep-link or check /my/ afterwards.
    """
    if request.method != "GET":
        return api_response(False, "Method not allowed", status=405)
    try:
        from apps.common.phonepay_utils import get_order_status

        merchant_order_id = request.GET.get("merchantOrderId", "").strip()
        if not merchant_order_id:
            return api_response(False, "merchantOrderId is required", status=400)

        sub = Subscription.objects(merchant_order_id=merchant_order_id).first()
        if not sub:
            return api_response(False, "Subscription record not found", status=404)

        result = get_order_status(merchant_order_id)
        if result.get("state") == "COMPLETED":
            _complete_subscription(sub, result.get("amount_rupees", 0))

        return api_response(True, "Payment status updated", {
            "state":           result.get("state"),
            "plan":            sub.plan,
            "billing_cycle":   sub.billing_cycle,
            "payment_status":  sub.payment_status,
            "end_date":        sub.end_date.isoformat() if sub.end_date else None,
        })
    except Exception as e:
        return api_response(False, str(e), status=500)


# ── 4. Webhook (server-to-server) ─────────────────────────────────────────────

@csrf_exempt
def webhook(request):
    """
    POST /api/subscriptions/webhook/
    PhonePe reliable server-to-server notification.
    Configure this URL in your PhonePe merchant dashboard.
    """
    if request.method != "POST":
        return api_response(False, "Method not allowed", status=405)
    try:
        from apps.common.phonepay_utils import parse_webhook_payload

        auth_header = request.headers.get("Authorization", "")
        result      = parse_webhook_payload(request.body, auth_header)

        if not result.get("valid"):
            return api_response(False, result.get("message", "Invalid webhook"), status=400)

        merchant_order_id = result.get("merchant_order_id")
        sub = Subscription.objects(merchant_order_id=merchant_order_id).first()
        if not sub:
            # Must return 200 so PhonePe doesn't keep retrying
            return api_response(True, "Acknowledged")

        if result.get("state") == "COMPLETED":
            _complete_subscription(sub, result.get("amount_rupees", 0))
        elif result.get("state") == "FAILED" and sub.payment_status == "PENDING":
            sub.payment_status = "FAILED"
            sub.save()

        return api_response(True, "Webhook processed")
    except Exception as e:
        return api_response(False, str(e), status=500)


# ── 5. My Subscription ────────────────────────────────────────────────────────

@csrf_exempt
@require_auth
def my_subscription(request):
    """
    GET /api/subscriptions/my/
    Returns the caller's most recent COMPLETED subscription, if any.
    """
    if request.method != "GET":
        return api_response(False, "Method not allowed", status=405)
    try:
        user_id = str(request.user.id)
        cp = ClientProfile.objects(user=user_id).first()

        # Latest completed subscription
        sub = Subscription.objects(
            user_id=user_id,
            payment_status="COMPLETED",
        ).order_by("-end_date").first()

        now = datetime.utcnow()
        is_active = bool(sub and sub.end_date and sub.end_date > now)

        return api_response(True, "Subscription fetched", {
            "current_plan":  cp.subscription_plan if cp else "SILVER",
            "is_active":     is_active,
            "plan":          sub.plan          if sub else None,
            "billing_cycle": sub.billing_cycle if sub else None,
            "amount":        sub.amount        if sub else None,
            "start_date":    sub.start_date.isoformat() if sub and sub.start_date else None,
            "end_date":      sub.end_date.isoformat()   if sub and sub.end_date   else None,
        })
    except Exception as e:
        return api_response(False, str(e), status=500)
