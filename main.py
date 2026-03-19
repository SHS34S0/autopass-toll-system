from sqlite3 import IntegrityError

from fastapi import FastAPI, Request, Form, Depends
from fastapi.staticfiles import (
    StaticFiles,
)  # this is used to serve static files like CSS, js, images, etc
from fastapi.templating import Jinja2Templates
import aiosqlite
from fastapi import Response
from werkzeug.security import generate_password_hash
from schemas import CarAddModel, UserRegisterModel, UserLoginModel
from pydantic import ValidationError
from contextlib import asynccontextmanager
from fastapi.responses import RedirectResponse
import os
import helpers as h
import messages as msg
import logging

logger = logging.getLogger(__name__)

logging.basicConfig(
    handlers=[
        logging.FileHandler("autopass.log", encoding="utf-8"),
        logging.StreamHandler()
    ],
    level=logging.WARNING,
    format="[%(asctime)s] [%(name)s] %(levelname)s (line %(lineno)d): %(message)s", )


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    file_exists = os.path.exists("db/database.db")
    fastapi_app.state.db = await aiosqlite.connect("db/database.db")

    if not file_exists:
        with open("db/schema.sql", "r", encoding="utf-8") as f:
            with open("db/insert_toll_stations.sql", "r", encoding="utf-8") as s:
                schema = f.read()
                station = s.read()
                await fastapi_app.state.db.executescript(schema)
                logger.warning(f"Database schema created")
                await fastapi_app.state.db.executescript(station)
                logger.warning(f"Database insert toll stations created")
                await fastapi_app.state.db.commit()
                logger.warning(f"Database committed")
    # pause the execution of the lifespan function until the app is shutting down
    yield
    # stop the execution of the lifespan function and continue with the shutdown process
    await fastapi_app.state.db.close()


app = FastAPI(lifespan=lifespan)


async def get_db(request: Request):
    return request.app.state.db


app.mount("/static", StaticFiles(directory="static"), name="static")
# jinja2 looks for templates in the "templates" directory
templates = Jinja2Templates(directory="templates")


@app.get("/add_vehicle", tags=["add_vehicle"])
async def add_car(
        request: Request, user_id: int = Depends(h.get_user_id)
):
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="add_vehicle.html", context={"user_id": user_id}
    )


@app.post("/add_vehicle", tags=["add_vehicle"])
async def process_add_car(
        request: Request,
        car_number: str = Form(),
        make: str = Form(),
        model: str = Form(),
        fuel_type: str = Form(),
        user_id: int = Depends(h.get_user_id),
        db=Depends(get_db),
):
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)

    try:
        car_data = CarAddModel(
            car_number=car_number, make=make, model=model, fuel_type=fuel_type
        )
    except ValidationError:
        logger.warning(f"Car {car_number} does not exist")
        return templates.TemplateResponse(
            request=request,
            name="add_vehicle.html",
            context={"error": msg.CarMessages.ERROR},
        )
    car_data.fuel_type = h.fuel_type_to_id(car_data.fuel_type)
    # Transaction
    try:
        await db.execute("BEGIN TRANSACTION")
        await db.execute(
            "INSERT INTO vehicles (car_num, fuel_type) VALUES (?, ?)",
            (car_data.car_number.upper(), car_data.fuel_type),
        )
        await db.execute(
            "INSERT INTO auto_pass (person_id, car_num) VALUES (?, ?)",
            (user_id, car_data.car_number.upper()),
        )
        await db.execute("COMMIT")
    except Exception as e:
        await db.execute("ROLLBACK")
        logger.error(e)
        return templates.TemplateResponse(
            request=request,
            name="add_vehicle.html",
            context={"error": msg.CarMessages.PLATE_EXISTS},
        )

    await h.generate_fake_passages(db, car_data.car_number.upper())

    h.get_own_vehicles.cache_clear()
    h.get_cost_this_month.cache_clear()
    h.get_all_passages.cache_clear()
    h.get_active_vehicles.cache_clear()

    return RedirectResponse(url="/dashboard", status_code=303)


@app.get("/dashboard", tags=["dashboard"])
async def dashboard(
        request: Request, user_id: int = Depends(h.get_user_id), db=Depends(get_db)
):
    if not user_id:
        return RedirectResponse(url="/", status_code=303)
    cars_info = await h.get_active_vehicles(db, user_id)
    if not cars_info:
        return RedirectResponse(url="/add_vehicle", status_code=303)

    # print(cars_info)
    # print(await h.get_all_passages(db, cars_info))
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "user_id": user_id,
            "cars_info": cars_info,
            "active_vehicles": len(cars_info),
            # need to pass the tuple for the cache to work
            "passages": await h.get_all_passages(db, tuple(cars_info)),
            "this_month_cost": await h.get_cost_this_month(db, tuple(cars_info)),
        },
    )


@app.get("/dashboard/{car_num}", tags=["dashboard"])
async def view_trips(
        request: Request, car_num: str, user_id: int = Depends(h.get_user_id), db=Depends(get_db)
):
    if not user_id:
        return RedirectResponse(url="/", status_code=303)
    if not await h.get_own_vehicles(db, user_id, car_num.replace("_", " ")):
        logger.warning(f"User {user_id} does not own {car_num}")
        return RedirectResponse(url="/dashboard", status_code=303)
    cars_info = await h.get_active_vehicles(db, user_id)
    if not cars_info:
        return RedirectResponse(url="/add_vehicle", status_code=303)
    # conversion is needed to use 2 existing functions rather than writing new ones
    car_num_raw = ((car_num.replace("_", " "),),)
    this_month_cost_1_car = await h.get_cost_this_month(db, car_num_raw)
    if not this_month_cost_1_car[0]:
        return RedirectResponse(url="/dashboard", status_code=303)
    #########################################
    # all_trips = await h.get_all_passages(db, car_num_raw)
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "user_id": user_id,
            "car_num": car_num.replace("_", " "),
            "cars_info": cars_info,
            "this_month_cost_1_car": this_month_cost_1_car,
            "passages": await h.get_all_passages(db, car_num_raw),
        },
    )


@app.get("/print/{car_num}", tags=["print"])
async def print_trips(
        request: Request, car_num: str, user_id: int = Depends(h.get_user_id), db=Depends(get_db)
):
    if not user_id:
        return RedirectResponse(url="/", status_code=303)
    if not car_num:
        return RedirectResponse(url="/dashboard", status_code=303)
    if not await h.get_own_vehicles(db, user_id, car_num.replace("_", " ")) and car_num != "all_trips":
        return RedirectResponse(url="/dashboard", status_code=303)
    # conversion is needed to use 2 existing functions rather than writing new ones
    car_num_raw = ((car_num.replace("_", " "),),)
    cars_info = await h.get_active_vehicles(db, user_id)
    # всі авто?
    all_trips = await h.get_all_passages(db, tuple(cars_info))
    if car_num != "all_trips":
        # конкретне
        all_trips = await h.get_all_passages(db, car_num_raw)
    pdf_content = bytes(h.create_trips_report(all_trips, "AutoPASS Trips"))
    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=trips_report.pdf"
        }
    )


@app.get("/finances", tags=["finances"])
async def render_page(request: Request, user_id: int | None = Depends(h.get_user_id), db=Depends(get_db)):
    if not user_id:
        return RedirectResponse(url="/", status_code=303)
    cars_info = await h.get_active_vehicles(db, user_id)
    if not cars_info:
        return RedirectResponse(url="/add_vehicle", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="finances.html",
        context={
            "user_id": user_id,
            "cars_info": cars_info,
            "active_vehicles": len(cars_info),
            # need to pass the tuple for the cache to work
            "this_month_cost": await h.get_cost_this_month(db, tuple(cars_info)),
        },
    )


@app.get("/", tags=["home"])
async def render_page(request: Request, user_id: int | None = Depends(h.get_user_id)):
    if user_id:
        return RedirectResponse(url="/dashboard", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="index.html",
    )


@app.get("/login", tags=["login"])
def render_page_login(request: Request, user_id: int | None = Depends(h.get_user_id)):
    if user_id:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(request=request, name="login.html")


@app.post("/login", tags=["login"])
async def process_login(
        request: Request,
        email: str = Form(),
        password: str = Form(),
        db=Depends(get_db),
):
    try:
        user_data = UserLoginModel(email=email, password=password)
    except ValidationError:
        logger.warning(f"User {email} failed")
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": msg.AuthMessages.INVALID_CREDENTIALS},
        )
    user_id = await h.check_user_id(user_data.email, user_data.password, db)
    if not user_id:
        logger.warning(f"User {email} failed")
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": msg.AuthMessages.INVALID_CREDENTIALS},
        )

    return h.create_access_token(user_id)


@app.get("/logout", tags=["login"])
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    return response


@app.get("/register", tags=["register"])
def render_page_register(
        request: Request, user_id: int | None = Depends(h.get_user_id)
):
    if user_id:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(request=request, name="register.html")


@app.post("/register", tags=["register"])
async def process_register(
        request: Request,
        first_name: str = Form(),
        last_name: str = Form(),
        email: str = Form(),
        password: str = Form(),
        confirmation: str = Form(),
        phone: str = Form(),
        db=Depends(get_db),
):
    try:
        # try to create a UserRegisterModel instance with the provided data
        user_data = UserRegisterModel(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=password,
            confirmation=confirmation,
            phone=phone,
        )

    except ValidationError:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={
                "error": msg.AuthMessages.PASSWORD_MISMATCH,
            },
        )

    password_hash = generate_password_hash(user_data.password)
    try:
        await db.execute(
            "INSERT INTO persons (first_name, last_name, email, hash, phone) VALUES (?, ?, ?, ?, ?)",
            (
                user_data.first_name,
                user_data.last_name,
                user_data.email,
                password_hash,
                user_data.phone,
            ),
        )
        await db.commit()
    except IntegrityError:
        logger.warning(f"User {email} already exists")
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={
                "error": msg.AuthMessages.EMAIL_EXISTS,
            },
        )
    user_id = await h.check_user_id(user_data.email, user_data.password, db)
    logger.warning(f"User {email} successfully registered")

    if not user_id:
        logger.error(f"User {email} failed")
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": msg.AuthMessages.AUTH_ERROR},
        )

    return h.create_access_token(user_id)
