from django.core.mail import send_mail
from django.conf import settings


def send_otp_email(email, otp):
    subject = "Your Nuvo Hosting OTP"
    message = f"""
    Your OTP is: {otp}
    This OTP will expire in 5 minutes.
    """

    send_mail(
        subject,
        message,
        settings.EMAIL_HOST_USER,
        [email],
        fail_silently=False,
    )