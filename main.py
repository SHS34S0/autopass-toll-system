from fastapi import FastAPI, Request, Form, Depends
from fastapi.staticfiles import (
    StaticFiles,
)  # this is used to serve static files like css, js, images, etc
from fastapi.templating import Jinja2Templates
import uvicorn
import aiosqlite
from werkzeug.security import generate_password_hash, check_password_hash

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


@app.get("/")
def render_page(request: Request):

    my_name = "Sergo"

    return templates.TemplateResponse(
        request=request, name="index.html", context={"username": my_name}
    )


@app.get("/login")
def render_page_login(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")


@app.post("/login")
async def process_login(
    request: Request, email: str = Form(), password: str = Form(), db=Depends(get_db)
):
    if not email or not password:
        return {"error": "Email and password are required"}
    print(email, password)
    cursor = await db.execute(
        "SELECT * FROM persons WHERE email = ?", (email.lower().strip(),)
    )

    row = await cursor.fetchall()
    # check if the email exists and if the password is correct
    if len(row) != 1 or not check_password_hash(row[0][4], password):
        return {"error": "Invalid email or password"}
    return {"message": "Login successful", "email": email}


@app.get("/registrer")
def render_page_registrer(request: Request):
    return templates.TemplateResponse(request=request, name="registrer.html")


@app.post("/registrer")
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
    if not email or not password:
        return {"error": "Email and password are required"}
    if password != confirmation:
        return {"error": "Passwords do not match"}

    if len(password) < 8:
        return {"error": "Password must be at least 8 characters long"}

    password_hash = generate_password_hash(password)

    await db.execute(
        "INSERT INTO persons (first_name, last_name, email, hash, phone) VALUES (?, ?, ?, ?, ?)",
        (
            first_name.capitalize().strip(),
            last_name.capitalize().strip(),
            email.lower().strip(),
            password_hash,
            phone,
        ),
    )
    await db.commit()
    return {"message": "User registered successfully", "email": email}


# if __name__ == "__main__":
#     uvicorn.run("main:app", reload=True)
