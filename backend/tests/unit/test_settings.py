"""Validación de configuración: secretos de desarrollo prohibidos en producción."""

import pytest
from pydantic import SecretStr, ValidationError

from app.settings import Settings


def test_produccion_rechaza_secretos_por_defecto() -> None:
    with pytest.raises(ValidationError, match="ADMIN_TOKEN"):
        Settings(environment="production")


def test_produccion_arranca_con_secretos_propios() -> None:
    s = Settings(
        environment="production",
        admin_token=SecretStr("un-token-largo-y-propio"),
        api_key_pepper=SecretStr("un-pepper-largo-y-propio"),
    )
    assert s.environment == "production"


def test_desarrollo_admite_valores_por_defecto() -> None:
    assert Settings(environment="development").admin_token.get_secret_value()
