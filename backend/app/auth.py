from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import settings
from .logging_config import hash_identifier
from .metrics import record_auth_failure
from .request_context import set_request_context
from .store import get_user_by_id

pwd_context = CryptContext(schemes=["bcrypt", "pbkdf2_sha256"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=True)

BCRYPT_MAX_BYTES = 72


def _password_bytes(password: str) -> bytes:
    return (password or "").encode("utf-8")


def password_too_long(password: str) -> bool:
    return len(_password_bytes(password)) > BCRYPT_MAX_BYTES


def hash_password(password: str) -> str:
    # bcrypt only uses first 72 bytes; we enforce a hard cap to avoid silent truncation
    # and to prevent passlib from raising a 500 at runtime.
    if password_too_long(password):
        raise ValueError("password_too_long")
    try:
        return pwd_context.hash(password)
    except Exception:
        # If bcrypt backend isn't available in the runtime, fall back to a pure-passlib hash.
        fallback = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
        return fallback.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    if password_too_long(password):
        return False
    try:
        return pwd_context.verify(password, password_hash)
    except Exception:
        return False


def create_access_token(user: dict) -> str:
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": user.get("role", "participant"),
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except JWTError as exc:
        record_auth_failure("invalid_token")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token") from exc

    user_id = payload.get("sub")
    if not user_id:
        record_auth_failure("invalid_token")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token")
    user = get_user_by_id(user_id)
    if not user:
        record_auth_failure("invalid_token")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token")
    set_request_context(user_hash=hash_identifier(user.get("id")))
    return {"id": user["id"], "email": user["email"], "role": user.get("role", "participant")}
