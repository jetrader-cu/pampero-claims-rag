"""Excepciones especializadas para el pipeline de ingesta de documentos."""


class IngestError(Exception):
    """Excepción base para errores de ingesta."""

    def __init__(self, message: str, code: str = "ingest_error", detail: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.detail = detail or message


class TransientIngestError(IngestError):
    """Error transitorio recuperable mediante reintento (ej. timeout de red, 429 de embeddings)."""

    def __init__(
        self,
        message: str,
        code: str = "transient_error",
        detail: str | None = None,
    ) -> None:
        super().__init__(message, code=code, detail=detail)


class PermanentIngestError(IngestError):
    """Error irrecuperable que no debe reintentarse (ej. PDF corrupto, cifrado o inválido)."""

    def __init__(
        self,
        message: str,
        code: str = "permanent_error",
        detail: str | None = None,
    ) -> None:
        super().__init__(message, code=code, detail=detail)
