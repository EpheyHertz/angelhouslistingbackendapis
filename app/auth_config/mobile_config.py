# Mobile app configuration
MOBILE_APP_SCHEMES = {
    "ios": "myapp://",
    "android": "myapp://"
}

def get_mobile_redirect_url(platform: str, access_token: str, token_type: str) -> str:
    """
    Generate a mobile app redirect URL based on the platform
    """
    base_url = MOBILE_APP_SCHEMES.get(platform.lower(), MOBILE_APP_SCHEMES["android"])
    return f"{base_url}auth?access_token={access_token}&token_type={token_type}"
