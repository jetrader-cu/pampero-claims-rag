"""Funciones de seguridad criptográfica y gestión de API Keys."""

import hashlib
import hmac
import secrets

from app.settings import get_settings


def hash_api_key(raw_key: str, pepper: str | None = None) -> bytes:
    """Calcula el hash HMAC-SHA256 de una clave de API con el pepper del sistema."""
    if pepper is None:
        pepper = get_settings().api_key_pepper.get_secret_value()
    return hmac.new(
        pepper.encode("utf-8"),
        raw_key.encode("utf-8"),
        hashlib.sha256,
    ).digest()


def generate_api_key(pepper: str | None = None) -> tuple[str, str, bytes]:
    """Genera una nueva API Key de usuario con formato pk_<prefijo>_<secreto>.

    Retorna:
        Una tupla con (raw_key, prefix, key_hash).
    """
    prefix = secrets.token_hex(4)  # 8 caracteres hexadecimales
    secret = secrets.token_urlsafe(32)
    raw_key = f"pk_{prefix}_{secret}"
    key_hash = hash_api_key(raw_key, pepper)
    return raw_key, prefix, key_hash


def verify_admin_token(token: str, expected_token: str | None = None) -> bool:
    """Compara en tiempo constante el token de administración recibido."""
    if expected_token is None:
        expected_token = get_settings().admin_token.get_secret_value()
    return secrets.compare_digest(token, expected_token)
