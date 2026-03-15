from fastapi import Request
import jwt
from werkzeug.security import check_password_hash
import config
from datetime import timezone
from fastapi.responses import RedirectResponse
from async_lru import alru_cache
import logging

logger = logging.getLogger(__name__)


async def check_user_id(email: str, password: str, db):
    cursor = await db.execute(
        "SELECT * FROM persons WHERE email = ?", (email.lower().strip(),)
    )

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


def fuel_type_to_id(fuel_type: str):
    fuel_types = {"gasoline": 1, "diesel": 1, "hybrid": 2, "electric": 3}
    return fuel_types.get(fuel_type)


import random
from datetime import datetime, timedelta


def get_random_date_in_past(days=30):
    max_seconds = days * 24 * 60 * 60
    random_seconds = random.randint(0, max_seconds)
    return datetime.now().replace(microsecond=0) - timedelta(seconds=random_seconds)


async def generate_fake_passages(db, car_number):
    try:
        passages = random.randint(5, 20)

        for i in range(passages):
            await db.execute(
                "INSERT INTO passages (car_num, station_id, passed_at) VALUES (?, ?, ?)",
                (car_number, random.randint(1, 10), get_random_date_in_past(30)),
            )
        await db.commit()

    except Exception as e:
        logger.error(e)
        return False
    return True


@alru_cache(maxsize=1000)
async def get_active_vehicles(db, user_id):
    cursor = await db.execute(
        """
        SELECT DISTINCT auto_pass.car_num, vehicles.fuel_type
        FROM auto_pass
                 JOIN vehicles ON auto_pass.car_num = vehicles.car_num
        WHERE auto_pass.person_id = ?
        """,
        (user_id,),
    )
    return await cursor.fetchall()


def generate_dynamic_query(car_list):
    car_numbers = []
    placeholders = []
    for car in car_list:
        car_numbers.append(car[0])
        placeholders.append("?")
    glue = " , "
    return glue.join(placeholders), car_numbers


@alru_cache(maxsize=1000)
async def get_all_passages(db, car_number_raw):
    placeholders, car_number = generate_dynamic_query(car_number_raw)
    cursor = await db.execute(
        f"SELECT passed_at, station, car_num, final_price_ore FROM all_passages WHERE car_num IN ({placeholders}) ORDER BY passed_at DESC LIMIT 50",
        car_number,
    )
    return await cursor.fetchall()


@alru_cache(maxsize=1000)
async def get_cost_this_month(db, car_number_raw):
    placeholders, car_number = generate_dynamic_query(car_number_raw)
    cursor = await db.execute(
        f"""
        SELECT SUM(base_price) AS total,
               SUM(final_price_ore) AS final
        FROM all_passages
        WHERE passed_at >= date('now','start of month')
          AND passed_at < date('now','start of month','+1 month')
          AND car_num IN ({placeholders})
        """,
        car_number
    )
    return await cursor.fetchone()


@alru_cache(maxsize=1000)
async def get_own_vehicles(db, user_id, car_num):
    cursor = await db.execute(
        """
        SELECT *
        FROM auto_pass
        WHERE person_id = ?
          AND car_num = ?
        """,
        (user_id, car_num),
    )
    return await cursor.fetchall()
