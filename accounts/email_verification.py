import secrets
from django.core.cache import cache
from django.core.mail import send_mail
from django.core.mail import BadHeaderError
from django.conf import settings



def generate_verification_token():
    return secrets.token_urlsafe(32)


VERIFICATION_TOKEN_EXPIRY = 15 * 60  # 15 minutes
RESEND_VERIFICATION_COOLDOWN = 5 * 60  # 5 minutes

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
    f"{settings.BACKEND_BASE_URL}/api/v1/auth/verify-email/?token={token}"
)

    print("EMAIL:", user.email)
    print("TOKEN:", token)
    print("LINK:", verification_link)
    
    try:
        send_mail(
            subject="Verify your BiteBazaar account",
            message=f"Click the link below to verify your email:\n\n{verification_link}",
            from_email=None,
            recipient_list=[user.email],
        )
    except BadHeaderError:
        raise
    
    except Exception as e:
        print("EMAIL SENDING FAILED:", e)
        raise
    


def resend_verification_email(user):
    token = generate_verification_token()

    store_verification_token(
        user.id,
        token
    )

    send_verification_email(
        user,
        token
    )
    
