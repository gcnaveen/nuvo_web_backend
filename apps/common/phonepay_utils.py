# apps/common/phonepay_utils.py
"""
PhonePe Payment Gateway — v2 API Utility
OAuth 2.0 (O-Bearer token) + direct REST calls via `requests`.
No external PhonePe SDK required.

Required env vars:
  PHONEPE_CLIENT_ID        — from PhonePe merchant dashboard
  PHONEPE_CLIENT_SECRET    — from PhonePe merchant dashboard
  PHONEPE_CLIENT_VERSION   — usually 1
  PHONEPE_ENV              — SANDBOX | PRODUCTION  (default: SANDBOX)
  PHONEPE_WEBHOOK_USERNAME — set in PhonePe dashboard webhook config
  PHONEPE_WEBHOOK_PASSWORD — set in PhonePe dashboard webhook config
"""
import hashlib, json, requests
from datetime import datetime, timedelta
from django.conf import settings


# ── Base URLs ──────────────────────────────────────────────────────────────────
_SANDBOX_BASE    = "https://api-preprod.phonepe.com/apis/pg-sandbox"
_PRODUCTION_BASE = "https://api.phonepe.com/apis/pg"


def _base() -> str:
    env = getattr(settings, "PHONEPE_ENV", "SANDBOX").upper()
    return _PRODUCTION_BASE if env == "PRODUCTION" else _SANDBOX_BASE


def _client_id()      -> str: return getattr(settings, "PHONEPE_CLIENT_ID",       "")
def _client_secret()  -> str: return getattr(settings, "PHONEPE_CLIENT_SECRET",   "")
def _client_version() -> int: return int(getattr(settings, "PHONEPE_CLIENT_VERSION", 1))
def _webhook_user()   -> str: return getattr(settings, "PHONEPE_WEBHOOK_USERNAME", "")
def _webhook_pass()   -> str: return getattr(settings, "PHONEPE_WEBHOOK_PASSWORD", "")


# ── OAuth token cache (module-level — reused within the same Lambda warm start)
_token_cache: dict = {"token": None, "expires_at": None}


def _get_oauth_token() -> str:
    """
    Fetch an O-Bearer token using client credentials grant.
    Result is cached in memory and auto-refreshed 60 s before expiry.
    """
    now = datetime.utcnow()
    if (
        _token_cache["token"]
        and _token_cache["expires_at"]
        and now < _token_cache["expires_at"]
    ):
        return _token_cache["token"]

    env = getattr(settings, "PHONEPE_ENV", "SANDBOX").upper()
    token_url = (
        "https://api.phonepe.com/apis/identity-manager/v1/oauth/token"
        if env == "PRODUCTION"
        else f"{_SANDBOX_BASE}/v1/oauth/token"
    )

    resp = requests.post(
        token_url,
        data={
            "client_id":      _client_id(),
            "client_secret":  _client_secret(),
            "client_version": _client_version(),
            "grant_type":     "client_credentials",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    token = data["access_token"]
    expires_at_epoch = data.get("expires_at")
    expires_at = (
        datetime.utcfromtimestamp(expires_at_epoch) - timedelta(seconds=60)
        if expires_at_epoch
        else now + timedelta(hours=1)
    )

    _token_cache["token"]      = token
    _token_cache["expires_at"] = expires_at
    return token


def _auth_header() -> str:
    return f"O-Bearer {_get_oauth_token()}"


# ── 1. Initiate Payment ────────────────────────────────────────────────────────

def initiate_payment(
    amount_rupees: float,
    merchant_order_id: str,
    redirect_url: str,
    user_mobile: str = None,
) -> dict:
    """
    Initiate a PhonePe v2 checkout payment.

    Args:
        amount_rupees:      Amount in INR (converted to paisa internally).
        merchant_order_id:  Unique ID from your system (max 63 chars,
                            only letters/digits/hyphen/underscore).
        redirect_url:       URL PhonePe redirects user to after payment.
                            For mobile: a deep link e.g. "nuvoapp://payment/result"
        user_mobile:        Optional — prefills user's mobile on PhonePe page.

    Returns dict:
        success           bool
        message           str
        redirect_url      str | None  ← open this in the mobile app / WebView
        phonepe_order_id  str | None  ← PhonePe's internal orderId
        merchant_order_id str         ← echo of input, used for status checks
    """
    payload = {
        "merchantOrderId": merchant_order_id,
        "amount":          int(round(amount_rupees * 100)),
        "expireAfter":     1800,    # 30 minutes
        "paymentFlow": {
            "type": "PG_CHECKOUT",
            "merchantUrls": {"redirectUrl": redirect_url},
        },
    }
    if user_mobile:
        payload["prefillUserLoginDetails"] = {"phoneNumber": str(user_mobile)}

    try:
        resp = requests.post(
            f"{_base()}/checkout/v2/pay",
            json=payload,
            headers={
                "Content-Type":  "application/json",
                "Authorization": _auth_header(),
            },
            timeout=15,
        )
        data = resp.json()
        if resp.status_code == 200:
            return {
                "success":           True,
                "message":           "Payment initiated",
                "redirect_url":      data.get("redirectUrl"),
                "phonepe_order_id":  data.get("orderId"),
                "merchant_order_id": merchant_order_id,
            }
        return {
            "success":           False,
            "message":           data.get("message", f"PhonePe error {resp.status_code}"),
            "redirect_url":      None,
            "phonepe_order_id":  None,
            "merchant_order_id": merchant_order_id,
        }
    except Exception as e:
        return {
            "success": False, "message": str(e),
            "redirect_url": None, "phonepe_order_id": None,
            "merchant_order_id": merchant_order_id,
        }


# ── 2. Get Order Status ────────────────────────────────────────────────────────

def get_order_status(merchant_order_id: str) -> dict:
    """
    Check the current status of a payment order.

    Returns dict:
        success       bool
        state         "PENDING" | "COMPLETED" | "FAILED"
        amount_rupees float
        message       str
    """
    try:
        resp = requests.get(
            f"{_base()}/checkout/v2/order/{merchant_order_id}/status",
            headers={
                "Content-Type":  "application/json",
                "Authorization": _auth_header(),
            },
            timeout=15,
        )
        data = resp.json()
        if resp.status_code == 200:
            return {
                "success":       True,
                "state":         data.get("state", "PENDING"),
                "amount_rupees": round(data.get("amount", 0) / 100, 2),
                "phonepe_order_id": data.get("orderId", ""),
                "message":       "Status fetched",
            }
        return {
            "success": False, "state": "FAILED", "amount_rupees": 0,
            "message": data.get("message", f"PhonePe error {resp.status_code}"),
        }
    except Exception as e:
        return {"success": False, "state": "FAILED", "amount_rupees": 0, "message": str(e)}


# ── 3. Webhook Verification & Parsing ─────────────────────────────────────────

def verify_webhook_signature(authorization_header: str) -> bool:
    """
    PhonePe sends: Authorization: SHA256(<username>:<password>)
    Verify it matches our configured credentials.
    """
    if not authorization_header:
        return False
    expected = "SHA256(" + hashlib.sha256(
        f"{_webhook_user()}:{_webhook_pass()}".encode()
    ).hexdigest() + ")"
    return authorization_header.strip() == expected


def parse_webhook_payload(body: bytes, authorization_header: str) -> dict:
    """
    Parse and validate a PhonePe v2 webhook POST.

    PhonePe webhook payload shape:
    {
        "event":   "checkout.order.completed" | "checkout.order.failed" | ...,
        "payload": {
            "merchantOrderId": "...",
            "orderId":         "...",
            "amount":          <paisa>,
            "state":           "COMPLETED" | "FAILED",
            ...
        }
    }

    Returns dict:
        valid             bool
        event             str
        merchant_order_id str
        phonepe_order_id  str
        state             "COMPLETED" | "FAILED"
        amount_rupees     float
        message           str
    """
    if not verify_webhook_signature(authorization_header):
        return {"valid": False, "message": "Webhook signature verification failed"}

    try:
        data    = json.loads(body)
        event   = data.get("event", "")
        payload = data.get("payload", {})
        state   = "COMPLETED" if event == "checkout.order.completed" else "FAILED"
        return {
            "valid":             True,
            "event":             event,
            "merchant_order_id": payload.get("merchantOrderId", ""),
            "phonepe_order_id":  payload.get("orderId", ""),
            "state":             state,
            "amount_rupees":     round(payload.get("amount", 0) / 100, 2),
            "message":           event,
        }
    except Exception as e:
        return {"valid": False, "message": str(e)}
