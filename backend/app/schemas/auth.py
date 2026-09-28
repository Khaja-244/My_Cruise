from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

class RegisterIn(StrictModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    phone: str | None = None

class LoginIn(StrictModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    phone: str | None
    role: str
    is_email_verified: bool
    must_change_password: bool = False

class TokenOut(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    user: UserOut

class RefreshOut(BaseModel):
    access_token: str
    token_type: str = 'bearer'

class ForgotIn(StrictModel):
    email: EmailStr

class VerifyOTPIn(StrictModel):
    email: EmailStr
    otp: str = Field(pattern='^\\d{6}$')

class ResetIn(StrictModel):
    reset_token: str
    new_password: str = Field(min_length=8, max_length=128)

class ChangePasswordIn(StrictModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)

class ProfilePatch(StrictModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
