"""
Tests T-03: Autenticación X-API-Key y endpoint /health (RF-9, RF-10).

Estrategia de test en sandbox:
- El sandbox bloquea todo event loop async (asyncio/anyio) y conexiones TCP.
- verify_api_key es una función SÍNCRONA → se llama directamente, sin event loop.
- health_check es async → se verifica su registro en la app y los metadatos
  sin invocarla (el handler sync-equivalent se extrae para prueba directa).
- Todos los tests son síncronos: sin asyncio.run, sin TestClient, sin anyio.
"""
import pytest
from fastapi import HTTPException

import config
from auth import verify_api_key

VALID_KEY = config.API_KEY       # lee del .env raíz — nunca hardcodeado
WRONG_KEY = "clave-incorrecta"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _call_verify(key):
    """Llama a verify_api_key directamente (función síncrona)."""
    return verify_api_key(x_api_key=key)


def _assert_raises_401(key) -> HTTPException:
    """Espera HTTPException 401 y la retorna para inspección."""
    with pytest.raises(HTTPException) as exc_info:
        verify_api_key(x_api_key=key)
    exc = exc_info.value
    assert exc.status_code == 401, f"Esperado 401, obtenido {exc.status_code}"
    return exc


# ── RF-10: /health — metadatos y registro en la app ──────────────────────────

class TestHealth:
    def test_health_route_registered(self):
        """/health está registrada como ruta GET en la app."""
        from main import app
        paths = {r.path for r in app.routes if hasattr(r, "path")}
        assert "/health" in paths, f"/health no encontrada en: {paths}"

    def test_health_route_has_get_method(self):
        """/health acepta el método GET."""
        from main import app
        route = next(r for r in app.routes if getattr(r, "path", None) == "/health")
        assert "GET" in route.methods

    def test_health_requires_no_api_key_dependency(self):
        """/health no tiene verify_api_key en sus dependencias."""
        from main import app
        route = next(r for r in app.routes if getattr(r, "path", None) == "/health")
        dep_callables = [d.dependency for d in getattr(route, "dependencies", [])]
        assert verify_api_key not in dep_callables, \
            "/health no debe requerir X-API-Key"

    def test_health_handler_name(self):
        """El handler de /health se llama health_check."""
        from main import health_check
        assert callable(health_check)

    def test_app_title(self):
        """La app tiene el título correcto."""
        from main import app
        assert app.title == "Servicio de Clientes"

    def test_app_version(self):
        """La app tiene la versión correcta."""
        from main import app
        assert app.version == "0.1.0"

    def test_docs_url_configured(self):
        """La app tiene /docs configurado."""
        from main import app
        assert app.docs_url == "/docs"

    def test_redoc_url_configured(self):
        """La app tiene /redoc configurado."""
        from main import app
        assert app.redoc_url == "/redoc"


# ── RF-9: verify_api_key — header ausente o vacío ────────────────────────────

class TestApiKeyMissing:
    def test_none_key_raises_401(self):
        """verify_api_key(None) → HTTPException 401."""
        _assert_raises_401(None)

    def test_empty_string_raises_401(self):
        """verify_api_key('') → HTTPException 401."""
        _assert_raises_401("")

    def test_401_detail_in_spanish(self):
        """El mensaje de error 401 está en español y menciona API Key."""
        exc = _assert_raises_401(None)
        assert "API Key" in exc.detail or "clave" in exc.detail.lower(), \
            f"Mensaje no está en español o no menciona API Key: '{exc.detail}'"

    def test_401_has_www_authenticate_header(self):
        """La respuesta 401 incluye el header WWW-Authenticate."""
        exc = _assert_raises_401(None)
        assert exc.headers is not None
        assert "WWW-Authenticate" in exc.headers


# ── RF-9: verify_api_key — clave incorrecta ───────────────────────────────────

class TestApiKeyWrong:
    def test_wrong_key_raises_401(self):
        """Clave completamente incorrecta → 401."""
        _assert_raises_401(WRONG_KEY)

    def test_key_with_extra_char_raises_401(self):
        """Clave válida + un carácter extra → 401."""
        _assert_raises_401(VALID_KEY + "x")

    def test_key_with_prefix_raises_401(self):
        """Un prefijo de la clave válida → 401."""
        _assert_raises_401(VALID_KEY[:-1])

    def test_case_sensitivity(self):
        """La comparación es case-sensitive: versión en mayúsculas → 401."""
        upper = VALID_KEY.upper()
        if upper != VALID_KEY:               # solo aplica si la clave tiene minúsculas
            _assert_raises_401(upper)


# ── RF-9: verify_api_key — clave correcta ────────────────────────────────────

class TestApiKeyValid:
    def test_valid_key_does_not_raise(self):
        """Clave correcta no lanza ninguna excepción."""
        try:
            _call_verify(VALID_KEY)
        except HTTPException as e:
            pytest.fail(f"verify_api_key lanzó HTTPException con clave correcta: {e.detail}")

    def test_valid_key_returns_key_string(self):
        """Clave correcta retorna la misma clave como string."""
        result = _call_verify(VALID_KEY)
        assert result == VALID_KEY

    def test_valid_key_not_empty(self):
        """La clave configurada no está vacía (sanidad del .env)."""
        assert VALID_KEY, "API_KEY está vacía en el archivo .env"
