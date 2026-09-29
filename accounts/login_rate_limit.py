import hashlib
from django.core.cache import cache

MAX_LOGIN_ATTEMPTS = 5
LOGIN_COOLDOWN_SECONDS = 15 * 60


def normalize_email(email):
    return email.lower().strip()


def get_login_attempt_key(email):
    normalized_email = normalize_email(email)

    email_hash = hashlib.sha256(
        normalized_email.encode()
    ).hexdigest()

    return f"login_attempts:{email_hash}"


def record_failed_login(email):
    key = get_login_attempt_key(email)

    attempts = cache.get(key, 0)
    attempts += 1

    cache.set(
        key,
        attempts,
        timeout=LOGIN_COOLDOWN_SECONDS
    )

    return attempts



def is_login_blocked(email):
    key = get_login_attempt_key(email)

    attempts = cache.get(key, 0)

    return attempts >= MAX_LOGIN_ATTEMPTS


def reset_login_attempts(email):
    key = get_login_attempt_key(email)

    cache.delete(key)