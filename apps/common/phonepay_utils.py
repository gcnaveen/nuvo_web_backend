# apps/common/phonepay_utils.py
"""
PhonePe Payment Gateway — Utility Stub
=======================================
Wire up real PhonePe SDK calls here when ready.
All views import from this module so no view code needs to change
when you switch from sandbox → production.

PhonePe Sandbox docs: https://developer.phonepe.com/v1/docs/

Environment variables expected in settings:
    PHONEPE_MERCHANT_ID
    PHONEPE_SALT_KEY
    PHONEPE_SALT_INDEX
    PHONEPE_BASE_URL       e.g. https://api-preprod.phonepe.com/apis/pg-sandbox
    PHONEPE_REDIRECT_URL   e.g. https://yourdomain.com/api/events/payment/callback/
    PHONEPE_CALLBACK_URL   e.g. https://yourdomain.com/api/events/payment/webhook/
"""

import hashlib
import base64
import json
import uuid

from django.conf import settings


# ─────────────────────────────────────────────────────────────
#  Internal helpers
# ─────────────────────────────────────────────────────────────

def _get_merchant_id() -> str:
    return getattr(settings, "PHONEPE_MERCHANT_ID", "PGTESTPAYUAT")


def _get_salt_key() -> str:
    return getattr(settings, "PHONEPE_SALT_KEY", "099eb0cd-02cf-4e2a-8aca-3e6c6aff0399")


def _get_salt_index() -> int:
    return int(getattr(settings, "PHONEPE_SALT_INDEX", 1))


def _get_base_url() -> str:
    return getattr(
        settings,
        "PHONEPE_BASE_URL",
        "https://api-preprod.phonepe.com/apis/pg-sandbox"
    )


def _compute_checksum(payload_base64: str, endpoint: str) -> str:
    """
    SHA256( base64(payload) + endpoint + salt_key ) + "###" + salt_index
    """
    salt_key   = _get_salt_key()
    salt_index = _get_salt_index()
    raw        = payload_base64 + endpoint + salt_key
    sha256     = hashlib.sha256(raw.encode()).hexdigest()
    return f"{sha256}###{salt_index}"


# ─────────────────────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────────────────────

def initiate_payment(
    amount_rupees: float,
    event_id: str,
    user_mobile: str = "9999999999",
) -> dict:
    """
    Build a PhonePe Pay Page initiation payload.

    Returns a dict with:
        success         : bool
        payment_url     : str  (redirect the user here)
        merchant_txn_id : str  (store this on the Event for callback lookup)
        message         : str

    TODO: Replace the stub return with a real `requests.post(...)` call
          to PhonePe's /pg/v1/pay endpoint.
    """
    merchant_id     = _get_merchant_id()
    merchant_txn_id = f"TXN-{event_id[:8].upper()}-{uuid.uuid4().hex[:6].upper()}"
    amount_paise    = int(amount_rupees * 100)   # PhonePe expects paise

    redirect_url = getattr(
        settings,
        "PHONEPE_REDIRECT_URL",
        f"http://localhost:8000/api/events/payment/callback/?txn={merchant_txn_id}"
    )
    callback_url = getattr(
        settings,
        "PHONEPE_CALLBACK_URL",
        "http://localhost:8000/api/events/payment/webhook/"
    )

    payload = {
        "merchantId":            merchant_id,
        "merchantTransactionId": merchant_txn_id,
        "merchantUserId":        f"USER-{event_id[:8]}",
        "amount":                amount_paise,
        "redirectUrl":           redirect_url,
        "redirectMode":          "REDIRECT",
        "callbackUrl":           callback_url,
        "mobileNumber":          user_mobile,
        "paymentInstrument": {
            "type": "PAY_PAGE"
        }
    }

    payload_json   = json.dumps(payload)
    payload_base64 = base64.b64encode(payload_json.encode()).decode()
    checksum       = _compute_checksum(payload_base64, "/pg/v1/pay")

    # ── STUB: return a mock response ────────────────────────
    # TODO: Replace this block with:
    #
    #   import requests
    #   response = requests.post(
    #       f"{_get_base_url()}/pg/v1/pay",
    #       json={"request": payload_base64},
    #       headers={
    #           "Content-Type":  "application/json",
    #           "X-VERIFY":      checksum,
    #           "X-MERCHANT-ID": merchant_id,
    #       },
    #       timeout=15,
    #   )
    #   data = response.json()
    #   pay_url = data["data"]["instrumentResponse"]["redirectInfo"]["url"]
    #   return {
    #       "success":         True,
    #       "payment_url":     pay_url,
    #       "merchant_txn_id": merchant_txn_id,
    #       "message":         "Payment initiated",
    #   }

    return {
        "success":         True,
        "payment_url":     f"https://mercury-uat.phonepe.com/transact/simulator?token=STUB_{merchant_txn_id}",
        "merchant_txn_id": merchant_txn_id,
        "message":         "STUB: Payment initiation ready. Wire up real API call to go live.",
        "debug": {
            "payload_base64": payload_base64,
            "checksum":       checksum,
            "endpoint":       f"{_get_base_url()}/pg/v1/pay",
        }
    }


def verify_payment(merchant_txn_id: str) -> dict:
    """
    Check the status of a transaction by merchant_txn_id.

    Returns a dict with:
        success        : bool
        status         : str  ("PAYMENT_SUCCESS" | "PAYMENT_PENDING" | "PAYMENT_ERROR")
        amount_rupees  : float
        message        : str

    TODO: Replace stub with real GET to PhonePe's /pg/v1/status/{mid}/{txn} endpoint.
    """
    merchant_id = _get_merchant_id()
    endpoint    = f"/pg/v1/status/{merchant_id}/{merchant_txn_id}"
    checksum    = _compute_checksum("", endpoint)

    # ── STUB ────────────────────────────────────────────────
    # TODO: Replace with:
    #
    #   import requests
    #   response = requests.get(
    #       f"{_get_base_url()}{endpoint}",
    #       headers={
    #           "Content-Type":  "application/json",
    #           "X-VERIFY":      checksum,
    #           "X-MERCHANT-ID": merchant_id,
    #       },
    #       timeout=15,
    #   )
    #   data = response.json()
    #   return {
    #       "success":       data.get("success", False),
    #       "status":        data["data"]["state"],
    #       "amount_rupees": data["data"]["amount"] / 100,
    #       "message":       data.get("message", ""),
    #   }

    return {
        "success":       True,
        "status":        "PAYMENT_SUCCESS",     # Stub always succeeds
        "amount_rupees": 0.0,
        "message":       "STUB: Verify payment — wire up real API call to go live.",
        "debug": {
            "endpoint": f"{_get_base_url()}{endpoint}",
            "checksum": checksum,
        }
    }


def parse_webhook_payload(request_body: bytes) -> dict:
    """
    Decode and verify an incoming PhonePe server-to-server webhook.

    Returns a dict with:
        valid          : bool
        merchant_txn_id: str
        status         : str
        amount_rupees  : float

    TODO: Implement real signature verification using X-VERIFY header.
    """
    try:
        data = json.loads(request_body)

        # TODO: Verify X-VERIFY signature from request headers before trusting payload.
        #
        # response_base64 = data.get("response", "")
        # received_checksum = request.headers.get("X-VERIFY", "")
        # expected = _compute_checksum(response_base64, "")  # PhonePe uses empty path for webhook
        # if received_checksum != expected:
        #     return {"valid": False, "message": "Checksum mismatch"}
        #
        # decoded = json.loads(base64.b64decode(response_base64).decode())
        # txn_id  = decoded["data"]["merchantTransactionId"]
        # status  = decoded["data"]["state"]
        # amount  = decoded["data"]["amount"] / 100

        return {
            "valid":           True,
            "merchant_txn_id": data.get("merchantTransactionId", ""),
            "status":          data.get("state", "PAYMENT_SUCCESS"),
            "amount_rupees":   data.get("amount", 0) / 100,
        }

    except Exception as e:
        return {"valid": False, "message": str(e)}