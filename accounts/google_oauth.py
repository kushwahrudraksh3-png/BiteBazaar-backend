from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from django.conf import settings
from urllib.parse import urlencode
import requests


def verify_google_token(token):
    try:
        idinfo = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )

        return idinfo

    except ValueError:
        return None
    
    
def get_google_user_info(idinfo):
    return {
        "google_id": idinfo.get("sub"),
        "email": idinfo.get("email"),
        "first_name": idinfo.get("given_name", ""),
        "last_name": idinfo.get("family_name", ""),
    }

def is_google_email_verified(idinfo):
    return idinfo.get("email_verified", False)



def get_google_authorization_url():

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": (
            "http://127.0.0.1:8000/"
            "api/v1/auth/google/callback/"
        ),
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }

    return (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        + urlencode(params)
    )
    
def exchange_google_code(code):

    token_url = "https://oauth2.googleapis.com/token"

    data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": (
            "http://127.0.0.1:8000/"
            "api/v1/auth/google/callback/"
        ),
        "grant_type": "authorization_code",
    }

    response = requests.post(
        token_url,
        data=data,
        timeout=10,
    )

    response.raise_for_status()

    return response.json()