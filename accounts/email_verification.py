import secrets
from django.core.cache import cache
from django.core.mail import send_mail




def generate_verification_token():
    return secrets.token_urlsafe(32)


VERIFICATION_TOKEN_EXPIRY = 15 * 60  # 15 minutes

def store_verification_token(user_id, token):
    key = f"email_verification:{token}"
    
    cache.set(
        key,
        user_id,
        timeout=VERIFICATION_TOKEN_EXPIRY
    )

def get_user_id_from_token(token):
    key = f"email_verification:{token}"

    return cache.get(key)

def delete_verification_token(token):
    key = f"email_verification:{token}"

    cache.delete(key)




def send_verification_email(user, token):
    verification_link = (
        f"http://127.0.0.1:8000/api/v1/auth/verify-email/?token={token}"
    )

    send_mail(
        subject="Verify your BiteBazaar account",
        message=f"Click the link below to verify your email:\n\n{verification_link}",
        from_email=None,
        recipient_list=[user.email],
    )