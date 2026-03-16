# apps/common/phonepay_utils.py
"""
PhonePe Payment Gateway — Sandbox Utility
Add to settings.py:
  PHONEPE_MERCHANT_ID  = "PGTESTPAYUAT"
  PHONEPE_SALT_KEY     = "<your-sandbox-salt>"
  PHONEPE_SALT_INDEX   = "1"
  PHONEPE_BASE_URL     = "https://api-preprod.phonepe.com/apis/pg-sandbox"
  PHONEPE_REDIRECT_URL = "https://yourdomain.com/api/events/payment/callback/"
  PHONEPE_CALLBACK_URL = "https://yourdomain.com/api/events/payment/webhook/"
"""
import base64, hashlib, json, uuid, requests
from django.conf import settings

def _cfg(k, d=""): return getattr(settings, k, d)
def _mid():  return _cfg("PHONEPE_MERCHANT_ID",  "PGTESTPAYUAT")
def _salt(): return _cfg("PHONEPE_SALT_KEY",     "")
def _idx():  return _cfg("PHONEPE_SALT_INDEX",   "1")
def _base(): return _cfg("PHONEPE_BASE_URL",     "https://api-preprod.phonepe.com/apis/pg-sandbox").rstrip("/")
def _redir():return _cfg("PHONEPE_REDIRECT_URL", "http://localhost:3000/payment/callback")
def _cb():   return _cfg("PHONEPE_CALLBACK_URL", "http://localhost:8000/api/events/payment/webhook/")

def _sha256(s): return hashlib.sha256(s.encode()).hexdigest()
def _checksum(b64, ep): return f"{_sha256(b64 + ep + _salt())}###{_idx()}"

def initiate_payment(amount_rupees, event_id, user_mobile="9999999999"):
    txn_id = f"NUVO-{event_id[:8].upper()}-{uuid.uuid4().hex[:8].upper()}"
    payload = {
        "merchantId": _mid(), "merchantTransactionId": txn_id,
        "merchantUserId": f"MUID-{event_id[:12]}",
        "amount": int(round(amount_rupees * 100)),
        "redirectUrl": f"{_redir()}?txn={txn_id}",
        "redirectMode": "REDIRECT", "callbackUrl": _cb(),
        "mobileNumber": user_mobile,
        "paymentInstrument": {"type": "PAY_PAGE"},
    }
    b64 = base64.b64encode(json.dumps(payload).encode()).decode()
    ep  = "/pg/v1/pay"
    try:
        r = requests.post(f"{_base()}{ep}", json={"request": b64},
            headers={"Content-Type":"application/json","X-VERIFY":_checksum(b64,ep),"X-MERCHANT-ID":_mid()}, timeout=15)
        d = r.json()
        if r.status_code == 200 and d.get("success"):
            url = d.get("data",{}).get("instrumentResponse",{}).get("redirectInfo",{}).get("url")
            return {"success":True,"message":"Payment initiated","payment_url":url,"merchant_txn_id":txn_id}
        return {"success":False,"message":d.get("message","PhonePe initiation failed"),"payment_url":None,"merchant_txn_id":txn_id}
    except Exception as e:
        return {"success":False,"message":str(e),"payment_url":None,"merchant_txn_id":txn_id}

def verify_payment(merchant_txn_id):
    ep = f"/pg/v1/status/{_mid()}/{merchant_txn_id}"
    cs = f"{_sha256(ep + _salt())}###{_idx()}"
    try:
        r = requests.get(f"{_base()}{ep}",
            headers={"Content-Type":"application/json","X-VERIFY":cs,"X-MERCHANT-ID":_mid()}, timeout=15)
        d = r.json()
        if r.status_code == 200 and d.get("success"):
            return {"success":True,"status":d.get("data",{}).get("state",""),
                    "amount_rupees":round(d.get("data",{}).get("amount",0)/100,2),"message":d.get("message","")}
        return {"success":False,"status":"PAYMENT_ERROR","amount_rupees":0,"message":d.get("message","")}
    except Exception as e:
        return {"success":False,"status":"PAYMENT_ERROR","amount_rupees":0,"message":str(e)}

def parse_webhook_payload(raw_body):
    try:
        body = json.loads(raw_body)
        b64  = body.get("response","")
        rcv  = body.get("X-VERIFY", body.get("x-verify",""))
        ep   = f"/pg/v1/status/{_mid()}"
        if f"{_sha256(b64 + ep + _salt())}###{_idx()}" != rcv:
            return {"valid":False,"message":"Checksum mismatch"}
        dec  = json.loads(base64.b64decode(b64).decode())
        pd   = dec.get("data",{})
        return {"valid":True,"status":pd.get("state","UNKNOWN"),
                "merchant_txn_id":pd.get("merchantTransactionId",""),
                "amount_rupees":round(pd.get("amount",0)/100,2),"message":dec.get("message","")}
    except Exception as e:
        return {"valid":False,"message":str(e)}