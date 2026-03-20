from fastapi import Request
import jwt
from werkzeug.security import check_password_hash
import config
from datetime import timezone
from fastapi.responses import RedirectResponse
import random
from datetime import datetime, timedelta
from async_lru import alru_cache
import logging
from fpdf import FPDF

logger = logging.getLogger(__name__)


class PDF(FPDF):
    def __init__(self, title_text, **kwargs):
        super().__init__(**kwargs)
        self.report_title = title_text

    def header(self):
        self.image("static/free-icon-a.png", 10, 5, 25)
        self.set_font("helvetica", "B", 15)
        self.cell(80)
        self.cell(30, 10, self.report_title, align="C")
        self.ln(25)

    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")


def create_trips_report(all_trips, header_title):
    pdf = PDF(title_text=header_title)
    pdf.add_page()
    pdf.set_font("Times", size=12)

    # table
    for i in all_trips:
        pdf.cell(47, 10, str(i[0]), border=1, align="C")
        pdf.cell(47, 10, str(i[1]), border=1, align="C")
        pdf.cell(47, 10, str(i[2]), border=1, align="C")
        pdf.cell(47, 10, str(i[3] / 100), border=1, align="C")
        pdf.ln()
    pdf.set_x(140)
    return pdf.output()


def rapport_month(tuple_text, header_title):
    pdf = PDF(title_text=header_title)
    pdf.add_page()
    pdf.set_font("Times", size=12)

    pdf.cell(200, 10, f"Total amount for {tuple_text[3]} {str(tuple_text[1] / 100)} NOK", align="C")
    pdf.ln(8)
    pdf.set_font("helvetica", "I", 11)
    pdf.cell(200, 10, f"Eco-saving bonus: {str(tuple_text[2] / 100)} NOK", align="C")
    pdf.set_text_color(0, 0, 0)
    return pdf.output()


async def check_user_id(email: str, password: str, db):
    cursor = await db.execute(
        "SELECT * FROM persons WHERE email = ?", (email.lower().strip(),)
    )

    row = await cursor.fetchone()
    try:

        # check if the email exists and if the password is correct
        if not check_password_hash(row[4], password):
            return False
        user_id: int = int(row[0])
        return user_id
    except Exception as e:
        logger.error(e)
        return False


def create_access_token(user_id: int):
    payload = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    token = jwt.encode(payload, config.SECRET_KEY, algorithm=config.ALGORITHM)
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(key="access_token", value=token, httponly=True)
    return response


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


def get_random_date_in_past(days=90):
    max_seconds = days * 24 * 60 * 60
    random_seconds = random.randint(0, max_seconds)
    return datetime.now().replace(microsecond=0) - timedelta(seconds=random_seconds)


async def generate_fake_passages(db, car_number):
    try:
        passages = random.randint(10, 40)

        for i in range(passages):
            await db.execute(
                "INSERT INTO passages (car_num, station_id, passed_at) VALUES (?, ?, ?)",
                (car_number, random.randint(1, 10), get_random_date_in_past(90)),
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
        f"SELECT passed_at, station, car_num, final_price_ore FROM all_passages WHERE car_num IN ({placeholders}) ORDER BY passed_at DESC",
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


async def all_months_info(db, car_number_raw):
    placeholders, car_number = generate_dynamic_query(car_number_raw)
    cursor = await db.execute(
        f"""
        SELECT passed_at,
       SUM(final_price_ore)                   AS total_month,
       SUM(base_price) - SUM(final_price_ore) AS saved,
       CASE
           WHEN strftime('%m', passed_at) = '01' THEN 'JANUARY'
           WHEN strftime('%m', passed_at) = '02' THEN 'FEBRUARY'
           WHEN strftime('%m', passed_at) = '03' THEN 'MARCH'
           WHEN strftime('%m', passed_at) = '04' THEN 'APRIL'
           WHEN strftime('%m', passed_at) = '05' THEN 'MAY'
           WHEN strftime('%m', passed_at) = '06' THEN 'JUNE'
           WHEN strftime('%m', passed_at) = '07' THEN 'JULY'
           WHEN strftime('%m', passed_at) = '08' THEN 'AUGUST'
           WHEN strftime('%m', passed_at) = '09' THEN 'SEPTEMBER'
           WHEN strftime('%m', passed_at) = '10' THEN 'OCTOBER'
           WHEN strftime('%m', passed_at) = '11' THEN 'NOVEMBER'
           WHEN strftime('%m', passed_at) = '12' THEN 'DECEMBER'
           END                                AS month
        FROM all_passages
        WHERE car_num IN ({placeholders})
        GROUP BY strftime('%Y', passed_at), strftime('%m', passed_at) ORDER BY passed_at DESC""", car_number
    )
    return await cursor.fetchall()
