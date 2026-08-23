"""密码哈希与 JWT。"""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(*, subject: str, extra: dict | None = None) -> str:
    settings = get_settings()
    payload = {
        "sub": subject,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes),
        **(extra or {}),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("无效令牌") from exc


def hash_device_api_key(raw_key: str) -> str:
    settings = get_settings()
    return pwd_context.hash(f"{settings.device_api_key_pepper}:{raw_key}")


def verify_device_api_key(raw_key: str, hashed: str) -> bool:
    settings = get_settings()
    return pwd_context.verify(f"{settings.device_api_key_pepper}:{raw_key}", hashed)
