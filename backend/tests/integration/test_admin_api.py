"""Pruebas de endpoints de administración y autenticación."""

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_flujo_completo_admin_crear_tenant_usuario_y_consultar_me(
    client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    """Verifica creación de tenant, aprovisionamiento de usuario y consulta en /me."""
    slug = f"tenant-test-{uuid.uuid4().hex[:6]}"

    # 1. Crear tenant
    resp_tenant = await client.post(
        "/api/v1/tenants",
        headers=admin_headers,
        json={"slug": slug, "name": "Aseguradora de Prueba"},
    )
    assert resp_tenant.status_code == 201
    tenant_data = resp_tenant.json()
    tenant_id = tenant_data["id"]
    assert tenant_data["slug"] == slug

    # 2. Crear usuario dentro del tenant
    resp_user = await client.post(
        f"/api/v1/tenants/{tenant_id}/users",
        headers=admin_headers,
        json={"email": f"agente@{slug}.es"},
    )
    assert resp_user.status_code == 201
    user_data = resp_user.json()
    api_key = user_data["api_key"]
    assert api_key.startswith("pk_")
    assert user_data["tenant_id"] == tenant_id

    # 3. Consultar /me con la API Key generada
    resp_me = await client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    assert resp_me.status_code == 200
    me_data = resp_me.json()
    assert me_data["user"]["email"] == f"agente@{slug}.es"
    assert me_data["tenant"]["slug"] == slug


@pytest.mark.asyncio
async def test_acceso_admin_sin_token_devuelve_401(
    client: AsyncClient,
) -> None:
    """Acceso a endpoints admin sin cabecera X-Admin-Token es rechazado con 401."""
    resp = await client.post(
        "/api/v1/tenants",
        json={"slug": "intruso", "name": "Intruso"},
    )
    assert resp.status_code == 401
    data = resp.json()
    assert data["code"] == "invalid_admin_token"


@pytest.mark.asyncio
async def test_acceso_me_con_clave_invalida_devuelve_401(
    client: AsyncClient,
) -> None:
    """Acceso a /me con Bearer token inventado devuelve 401."""
    resp = await client.get(
        "/api/v1/me",
        headers={"Authorization": "Bearer pk_invalido_clave_inexistente"},
    )
    assert resp.status_code == 401
    data = resp.json()
    assert data["code"] == "invalid_api_key"
