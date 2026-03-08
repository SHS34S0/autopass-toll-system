from fastapi import Request
import jwt
import config


def get_user_id(request: Request):
    token = request.cookies.get("access_token")

    if not token:
        return None
    try:
        # encrypt
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        return payload.get("user_id")
    except jwt.InvalidTokenError:
        return None
