from fastapi import FastAPI, Request, Form, Depends
from fastapi.staticfiles import (
    StaticFiles,
)  # this is used to serve static files like css, js, images, etc
from fastapi.templating import Jinja2Templates
import uvicorn
import aiosqlite
from werkzeug.security import generate_password_hash, check_password_hash
from schemas import UserRegisterModel, UserLoginModel
from pydantic import ValidationError

import helpers as h


async def lifespan(app: FastAPI):
    app.state.db = await aiosqlite.connect("database.db")
    # pause the execution of the lifespan function until the app is shutting down
    yield
    # stop the execution of the lifespan function and continue with the shutdown process
    await app.state.db.close()


app = FastAPI(lifespan=lifespan)


async def get_db(request: Request):
    return request.app.state.db


app.mount("/static", StaticFiles(directory="static"), name="static")
# jinja2 looks for templates in the "templates" directory
templates = Jinja2Templates(directory="templates")


@app.get("/", tags=["home"])
def render_page(request: Request):

    my_name = "Sergo"

    return templates.TemplateResponse(
        request=request, name="index.html", context={"username": my_name}
    )


@app.get("/login", tags=["login"])
def render_page_login(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")


@app.post("/login", tags=["login"])
async def process_login(
    request: Request, email: str = Form(), password: str = Form(), db=Depends(get_db)
):

    try:
        user_data = UserLoginModel(email=email, password=password)
    except ValidationError as e:
        return {"error": "Validation error", "details": e.errors()}

    cursor = await db.execute(
        "SELECT * FROM persons WHERE email = ?", (user_data.email.lower().strip(),)
    )

    row = await cursor.fetchall()
    # check if the email exists and if the password is correct
    if len(row) != 1 or not check_password_hash(row[0][4], user_data.password):
        return {"error": "Invalid email or password"}
    return {"message": "Login successful", "email": email}


@app.get("/registrer", tags=["registrer"])
def render_page_registrer(request: Request):
    return templates.TemplateResponse(request=request, name="registrer.html")


@app.post("/registrer", tags=["registrer"])
async def process_registrer(
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

    except ValidationError as e:
        return {"error": "Validation error", "details": e.errors()}

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
    return {"message": "User registered successfully", "email": user_data.email}


# if __name__ == "__main__":
#     uvicorn.run("main:app", reload=True)
