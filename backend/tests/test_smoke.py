"""Pruebas de humo iniciales del backend."""


def test_entorno_backend_carga_correctamente() -> None:
    """Verifica que el entorno de pruebas del backend está operativo."""
    import app

    assert app is not None
