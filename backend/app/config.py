"""应用配置：从环境变量加载。"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """运行时配置。"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="development", alias="APP_ENV")
    database_url: str = Field(
        default="postgresql+psycopg://gym:gym_dev_password@localhost:5432/gym",
        alias="DATABASE_URL",
    )
    secret_key: str = Field(default="dev-secret-change-me", alias="SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=720, alias="JWT_EXPIRE_MINUTES")
    cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:8080,http://localhost:8081,http://localhost:5174",
        alias="CORS_ORIGINS",
    )
    device_api_key_pepper: str = Field(default="device-pepper", alias="DEVICE_API_KEY_PEPPER")
    online_payment_mode: str = Field(default="unconfigured", alias="ONLINE_PAYMENT_MODE")
    wechat_app_id: str = Field(default="", alias="WECHAT_APP_ID")
    wechat_mch_id: str = Field(default="", alias="WECHAT_MCH_ID")
    wechat_api_key: str = Field(default="", alias="WECHAT_API_KEY")
    wechat_notify_url: str = Field(default="", alias="WECHAT_NOTIFY_URL")
    wechat_dry_run: bool = Field(default=True, alias="WECHAT_DRY_RUN")
    rabbitmq_url: str = Field(default="amqp://guest:guest@localhost:5672/", alias="RABBITMQ_URL")
    enable_rabbitmq: bool = Field(default=False, alias="ENABLE_RABBITMQ")
    # 会员验证码：mock | http | disabled
    member_otp_mode: str = Field(default="mock", alias="MEMBER_OTP_MODE")
    member_otp_mock_code: str = Field(default="123456", alias="MEMBER_OTP_MOCK_CODE")
    member_otp_mock_enabled: bool = Field(default=True, alias="MEMBER_OTP_MOCK_ENABLED")
    member_otp_sms_url: str = Field(default="", alias="MEMBER_OTP_SMS_URL")
    member_otp_sms_token: str = Field(default="", alias="MEMBER_OTP_SMS_TOKEN")

    seed_admin_username: str = Field(default="admin", alias="SEED_ADMIN_USERNAME")
    seed_admin_password: str = Field(default="Admin@123456", alias="SEED_ADMIN_PASSWORD")
    seed_admin_display_name: str = Field(default="场地超管", alias="SEED_ADMIN_DISPLAY_NAME")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
