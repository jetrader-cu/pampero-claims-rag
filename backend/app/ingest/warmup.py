"""Precarga los modelos de Docling y OCR durante el build de la imagen del worker.

Sin este paso, el primer documento descargaría los modelos de layout, tablas y OCR en
tiempo de ejecución: lento, dependiente de la red y difícil de reproducir.

Uso: python -m app.ingest.warmup
"""

import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from app.ingest.parsing import DoclingParser


def main() -> None:
    """Convierte un PDF de imagen mínimo para forzar la descarga de todos los modelos."""
    img = Image.new("RGB", (1240, 1754), "white")
    ImageDraw.Draw(img).text((100, 100), "Pampero warmup OCR 123", fill="black")
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = Path(tmp) / "warmup.pdf"
        img.save(pdf_path, "PDF", resolution=150)
        parsed = DoclingParser().parse(pdf_path)
    print(f"Docling listo: {parsed.page_count} página, OCR={parsed.ocr_used}")


if __name__ == "__main__":
    main()
