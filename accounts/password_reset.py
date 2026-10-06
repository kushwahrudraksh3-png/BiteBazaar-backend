import secrets
from django.core.cache import cache
from django.core.mail import send_mail
from django.core.mail import BadHeaderError



RESET_OTP_EXPIRY = 10 * 60
RESET_TOKEN_EXPIRY = 5 * 60

def generate_reset_otp():
    return f"{secrets.randbelow(1_000_000):06d}"


def store_reset_otp(email,otp):
    key = f"password_reset_otp:{email.lower().strip()}"
    cache.set(key, otp, timeout=RESET_OTP_EXPIRY)
    
def get_reset_otp(email):
    key = f"password_reset_otp:{email.lower().strip()}"
    return cache.get(key)


def delete_reset_otp(email):
    key = f"password_reset_otp:{email.lower().strip()}"
    cache.delete(key)
    
    
def verify_reset_otp(email, otp):
    stored_otp = get_reset_otp(email)

    if not stored_otp:
        return False

    if stored_otp != otp:
        return False

    return True



def generate_reset_token():
    return secrets.token_urlsafe(32)


def store_reset_token(email, token):
    key = f"password_reset_token:{email.lower().strip()}"
    cache.set(key, token, timeout=RESET_TOKEN_EXPIRY)
    

def get_reset_token(email):
    key = f"password_reset_token:{email.lower().strip()}"
    return cache.get(key)


def delete_reset_token(email):
    key = f"password_reset_token:{email.lower().strip()}"
    cache.delete(key)
    
    
    
def verify_reset_token(email, token):
    stored_token = get_reset_token(email)

    if not stored_token:
        return False

    if stored_token != token:
        return False

    return True


def send_reset_otp_email(user, otp):
    try:
        send_mail(
            subject="BiteBazaar Password Reset OTP",
            message=(
                f"Your BiteBazaar password reset OTP is: {otp}\n\n"
                "This OTP is valid for 10 minutes."
            ),
            from_email=None,
            recipient_list=[user.email],
        )
    except BadHeaderError:
        raise
    except Exception as e:
        print("PASSWORD RESET EMAIL FAILED:", e)
        raise
