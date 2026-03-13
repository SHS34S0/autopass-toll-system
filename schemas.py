from pydantic import (
    BaseModel,
    Field,
    EmailStr,
    ConfigDict,
    model_validator,
    field_validator,
)


class UserRegisterModel(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    confirmation: str = Field(min_length=8, max_length=128)
    phone: str = Field(pattern=r"^\+?1?\d{8,15}$")
    # model rules
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def check_passwords_match(self):
        if self.password != self.confirmation:
            raise ValueError("Passwords do not match")
        return self

    # formatting validators
    @field_validator("first_name", "last_name")
    @classmethod
    def format_names(cls, value: str):
        return value.capitalize().strip()

    @field_validator("email")
    @classmethod
    def format_email(cls, value: str):
        return value.lower().strip()


class UserLoginModel(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    model_config = ConfigDict(extra="forbid")


class CarAddModel(BaseModel):
    car_number: str = Field(pattern=r"^[A-Za-z]{2}\s?\d{1,5}$")
    make: str = Field(min_length=2, max_length=128)
    model: str = Field(min_length=2, max_length=128)
    fuel_type: str = Field(min_length=2, max_length=128)

    model_config = ConfigDict(extra="forbid")
