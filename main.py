from fastapi import FastAPI, Request, Form, Depends
from fastapi.staticfiles import (
    StaticFiles,
)  # this is used to serve static files like CSS, js, images, etc
from fastapi.templating import Jinja2Templates
import aiosqlite
from werkzeug.security import generate_password_hash
from schemas import UserRegisterModel, UserLoginModel
from pydantic import ValidationError
from contextlib import asynccontextmanager
from fastapi.responses import RedirectResponse
import helpers as h
import messages as msg


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    fastapi_app.state.db = await aiosqlite.connect("database.db")
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


@app.get("/dashboard", tags=["dashboard"])
async def dashboard(request: Request, user_id: int = Depends(h.get_user_id), db=Depends(get_db)):
    if not user_id:
        return RedirectResponse(url="/", status_code=303)
    cursor = await db.execute("SELECT * FROM persons WHERE id = ?", (user_id,))
    row = await cursor.fetchone()
    if not row:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": msg.AuthMessages.AUTH_ERROR},
        )
    name = row[1]

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"username": name, "user_id": user_id},
    )


@app.get("/", tags=["home"])
async def render_page(
        request: Request, user_id: int | None = Depends(h.get_user_id)
):
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
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": msg.AuthMessages.INVALID_CREDENTIALS}
        )
    user_id = await h.check_user_id(user_data.email, user_data.password, db)
    if not user_id:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": msg.AuthMessages.INVALID_CREDENTIALS}
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
async def process_register(request: Request,
                           first_name: str = Form(),
                           last_name: str = Form(),
                           email: str = Form(),
                           password: str = Form(),
                           confirmation: str = Form(),
                           phone: str = Form(),
                           db=Depends(get_db),
                           ):
    # check user exist
    if await h.user_exists(email, db):
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={
                "error": msg.AuthMessages.EMAIL_EXISTS,
            }
        )
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
            }
        )

    password_hash = generate_password_hash(user_data.password)

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
    user_id = await h.check_user_id(user_data.email, user_data.password, db)

    if not user_id:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": msg.AuthMessages.AUTH_ERROR},
        )
    return h.create_access_token(user_id)
