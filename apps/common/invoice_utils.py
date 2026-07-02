# apps/common/invoice_utils.py
"""
Invoice PDF generation for Nuvo Hosting event bookings.

Flow:
  1. generate_invoice_pdf(event) → bytes (PDF)
  2. upload to S3 at invoices/<event_id>/<invoice_number>.pdf
  3. email PDF to client
  4. store invoice_url + invoice_number on event.payment

Entry point: generate_and_deliver_invoice(event)
"""
import io, uuid
from datetime import datetime

from django.conf import settings
from django.core.mail import EmailMessage


# ── PDF builder ────────────────────────────────────────────────────────────────

def generate_invoice_pdf(event) -> bytes:
    """Return raw PDF bytes for the given Event."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT

    buf    = io.BytesIO()
    doc    = SimpleDocTemplate(buf, pagesize=A4,
                               leftMargin=20*mm, rightMargin=20*mm,
                               topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    story  = []

    navy   = colors.HexColor("#1a3c6e")
    gold   = colors.HexColor("#d4a020")
    light  = colors.HexColor("#f5f5f5")

    h1 = ParagraphStyle("h1", parent=styles["Heading1"],
                         textColor=navy, fontSize=22, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"],
                         textColor=navy, fontSize=13, spaceAfter=2)
    sm = ParagraphStyle("sm", parent=styles["Normal"], fontSize=9, spaceAfter=2)
    rt = ParagraphStyle("rt", parent=styles["Normal"], fontSize=9, alignment=TA_RIGHT)

    # ── Header ──────────────────────────────────────────────────
    story.append(Paragraph("NUVO HOSTING", h1))
    story.append(Paragraph("Premium Event Management", sm))
    story.append(Spacer(1, 6*mm))

    inv_num  = event.payment.invoice_number or _invoice_number(event)
    inv_date = datetime.utcnow().strftime("%d %b %Y")
    story.append(Paragraph(f"<b>INVOICE</b>", h2))
    story.append(Table(
        [["Invoice No:", inv_num, "Date:", inv_date]],
        colWidths=[30*mm, 70*mm, 20*mm, 40*mm],
        style=TableStyle([
            ("FONTSIZE",     (0,0), (-1,-1), 9),
            ("TEXTCOLOR",    (0,0), (0,0),   navy),
            ("TEXTCOLOR",    (0,0), (2,0),   navy),
            ("FONTNAME",     (0,0), (0,0),   "Helvetica-Bold"),
            ("FONTNAME",     (2,0), (2,0),   "Helvetica-Bold"),
        ])
    ))
    story.append(Spacer(1, 6*mm))

    # ── Client info ─────────────────────────────────────────────
    story.append(Paragraph("<b>Billed To</b>", h2))
    try:
        from apps.common.utils_helpers import safe_ref
        client_doc = event.client
        client_name = getattr(client_doc, "full_name", "—") or "—"
        try:
            user_doc  = client_doc.user
            client_email = getattr(user_doc, "email", "—") or "—"
            client_phone = getattr(user_doc, "phone_number", "—") or "—"
        except Exception:
            client_email = "—"
            client_phone = "—"
    except Exception:
        client_name = client_email = client_phone = "—"

    story.append(Paragraph(f"{client_name}", sm))
    story.append(Paragraph(f"Email: {client_email}", sm))
    story.append(Paragraph(f"Phone: {client_phone}", sm))
    story.append(Spacer(1, 6*mm))

    # ── Event details ────────────────────────────────────────────
    story.append(Paragraph("<b>Event Details</b>", h2))
    venue_name = ""
    try:
        venue_name = event.venue.venue_name or ""
    except Exception:
        pass

    event_date = ""
    try:
        event_date = event.event_start_datetime.strftime("%d %b %Y, %I:%M %p")
    except Exception:
        pass

    story.append(Table(
        [
            ["Event",    event.event_name or "—"],
            ["Type",     event.event_type  or "—"],
            ["Date",     event_date],
            ["Venue",    venue_name],
            ["Duration", f"{event.no_of_days or 1} day(s), {event.working_hours or 8} hrs/day"],
        ],
        colWidths=[35*mm, 125*mm],
        style=TableStyle([
            ("FONTSIZE",      (0,0), (-1,-1), 9),
            ("BACKGROUND",    (0,0), (0,-1),  light),
            ("FONTNAME",      (0,0), (0,-1),  "Helvetica-Bold"),
            ("TEXTCOLOR",     (0,0), (0,-1),  navy),
            ("ROWBACKGROUNDS",(0,0), (-1,-1), [light, colors.white]),
            ("GRID",          (0,0), (-1,-1), 0.25, colors.lightgrey),
            ("TOPPADDING",    (0,0), (-1,-1), 3),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ])
    ))
    story.append(Spacer(1, 6*mm))

    # ── Package breakdown ────────────────────────────────────────
    story.append(Paragraph("<b>Package Breakdown</b>", h2))
    rows = [["Package", "Count", "Rate / Person", "Subtotal"]]

    p = event.payment
    pkg_type = event.package_type or ""

    try:
        from apps.master.models import CrewPackage
        if pkg_type in ("LUXURY", "BOTH") and event.luxury_crew_count:
            lux = CrewPackage.objects(type="LUXURY").first()
            lux_price = lux.price_per_person if lux else 0
            rows.append([
                "Luxury", str(event.luxury_crew_count),
                f"₹{lux_price:,.0f}",
                f"₹{lux_price * event.luxury_crew_count:,.0f}",
            ])
        if pkg_type in ("PREMIUM", "BOTH") and event.premium_crew_count:
            pre = CrewPackage.objects(type="PREMIUM").first()
            pre_price = pre.price_per_person if pre else 0
            rows.append([
                "Premium", str(event.premium_crew_count),
                f"₹{pre_price:,.0f}",
                f"₹{pre_price * event.premium_crew_count:,.0f}",
            ])
    except Exception:
        pass

    story.append(Table(
        rows,
        colWidths=[50*mm, 25*mm, 45*mm, 40*mm],
        style=TableStyle([
            ("FONTSIZE",      (0,0), (-1,-1), 9),
            ("BACKGROUND",    (0,0), (-1,0),  navy),
            ("TEXTCOLOR",     (0,0), (-1,0),  colors.white),
            ("FONTNAME",      (0,0), (-1,0),  "Helvetica-Bold"),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [light, colors.white]),
            ("GRID",          (0,0), (-1,-1), 0.25, colors.lightgrey),
            ("ALIGN",         (1,0), (-1,-1), "CENTER"),
            ("TOPPADDING",    (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ])
    ))
    story.append(Spacer(1, 6*mm))

    # ── Totals ───────────────────────────────────────────────────
    gst    = p.gst_amount   or 0
    tax    = p.tax_amount   or 0
    total  = p.total_amount or 0
    paid   = p.paid_amount  or 0
    bal    = max(0, total - paid)

    totals = [
        ["Subtotal",        f"₹{(total - gst - tax):,.2f}"],
        ["GST",             f"₹{gst:,.2f}"],
        ["Tax",             f"₹{tax:,.2f}"],
        ["Total",           f"₹{total:,.2f}"],
        ["Paid",            f"₹{paid:,.2f}"],
        ["Balance Due",     f"₹{bal:,.2f}"],
    ]
    story.append(Table(
        totals,
        colWidths=[120*mm, 40*mm],
        hAlign="RIGHT",
        style=TableStyle([
            ("FONTSIZE",      (0,0), (-1,-1), 9),
            ("ALIGN",         (1,0), (1,-1),  "RIGHT"),
            ("FONTNAME",      (0,3), (-1,3),  "Helvetica-Bold"),
            ("FONTNAME",      (0,5), (-1,5),  "Helvetica-Bold"),
            ("TEXTCOLOR",     (0,5), (-1,5),  navy),
            ("LINEABOVE",     (0,3), (-1,3),  1, navy),
            ("TOPPADDING",    (0,0), (-1,-1), 3),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ])
    ))

    story.append(Spacer(1, 10*mm))
    story.append(Paragraph(
        "Thank you for choosing Nuvo Hosting. For queries contact us at support@nuvohosting.com",
        ParagraphStyle("footer", parent=styles["Normal"], fontSize=8,
                       textColor=colors.grey, alignment=TA_CENTER)
    ))

    doc.build(story)
    return buf.getvalue()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _invoice_number(event) -> str:
    prefix = "NVH"
    date   = datetime.utcnow().strftime("%Y%m")
    short  = str(event.id)[:6].upper()
    return f"{prefix}-{date}-{short}"


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_and_deliver_invoice(event) -> str:
    """
    Generate PDF, upload to S3, email client, update event.payment.
    Returns the S3 public URL of the invoice.
    Called from payment_callback and payment_webhook after COMPLETED state.
    """
    from apps.common.s3_utils import upload_file_to_s3

    # Skip if invoice already generated
    if event.payment and event.payment.invoice_url:
        return event.payment.invoice_url

    try:
        # 1. Generate PDF
        pdf_bytes = generate_invoice_pdf(event)

        # 2. Upload to S3
        inv_num  = _invoice_number(event)
        filename = f"{inv_num}.pdf"

        import io as _io
        file_obj = _io.BytesIO(pdf_bytes)
        file_obj.name = filename
        file_obj.content_type = "application/pdf"

        invoice_url = upload_file_to_s3(file_obj, folder="invoices")

        # 3. Update event payment record
        event.payment.invoice_url    = invoice_url
        event.payment.invoice_number = inv_num
        event.save()

        # 4. Email to client
        _email_invoice(event, pdf_bytes, inv_num)

        return invoice_url

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Invoice generation failed for event {event.id}: {e}")
        return ""


def _email_invoice(event, pdf_bytes: bytes, inv_num: str):
    """Send the invoice PDF to the client's email address."""
    try:
        client_email = ""
        client_name  = ""
        try:
            cp = event.client
            client_name = getattr(cp, "full_name", "") or ""
            user = cp.user
            client_email = getattr(user, "email", "") or ""
        except Exception:
            pass

        if not client_email:
            return

        subject = f"Your Nuvo Hosting Invoice — {inv_num}"
        body    = (
            f"Dear {client_name or 'Customer'},\n\n"
            f"Thank you for booking with Nuvo Hosting!\n\n"
            f"Please find your invoice ({inv_num}) attached to this email.\n\n"
            f"Event: {event.event_name}\n"
            f"Amount Paid: ₹{event.payment.paid_amount:,.2f}\n\n"
            f"For any queries, reply to this email or contact support@nuvohosting.com.\n\n"
            f"Warm regards,\nNuvo Hosting Team"
        )

        email = EmailMessage(subject=subject, body=body,
                             to=[client_email])
        email.attach(f"{inv_num}.pdf", pdf_bytes, "application/pdf")
        email.send(fail_silently=True)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Invoice email failed: {e}")
