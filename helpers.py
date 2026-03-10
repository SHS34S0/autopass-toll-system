from fastapi import Request
import jwt
from werkzeug.security import check_password_hash
import config
from datetime import datetime, timedelta, timezone
from fastapi.responses import RedirectResponse


async def check_user_id(email: str, password: str, db):
    cursor = await db.execute(
        "SELECT * FROM persons WHERE email = ?", (email.lower().strip(),))

    row = await cursor.fetchall()
    # check if the email exists and if the password is correct
    if len(row) != 1 or not check_password_hash(row[0][4], password):
        return False
    user_id: int = int(row[0][0])
    return user_id


def create_access_token(user_id: int):
    payload = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    token = jwt.encode(payload, config.SECRET_KEY, algorithm=config.ALGORITHM)
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(key="access_token", value=token, httponly=True)
    return response


async def user_exists(email, db):
    cursor = await db.execute(
        "SELECT * FROM persons WHERE email = ?", (email.lower().strip(),)
    )
    result = await cursor.fetchone() is not None
    return True if result else False


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
