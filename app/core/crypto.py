from functools import lru_cache

from cryptography.fernet import Fernet

from app.core.settings import settings


@lru_cache
def _fernet() -> Fernet:
    if not settings.figma_token_encryption_key:
        raise RuntimeError(
            "FIGMA_TOKEN_ENCRYPTION_KEY is not set — generate one with `python -c "
            '"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`'
        )
    return Fernet(settings.figma_token_encryption_key.encode())


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    return _fernet().decrypt(value.encode()).decode()
