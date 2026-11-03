"""Generador de documentos PDF de muestra para pruebas de ingesta y evaluación RAG."""

from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def generar_poliza_auto(dest: Path) -> None:
    c = canvas.Canvas(str(dest), pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, "PÓLIZA DE SEGURO DE AUTOMÓVILES - TODO RIESGO")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 710, "CONDICIONES GENERALES")

    c.setFont("Helvetica", 10)
    c.drawString(50, 680, "Tomador: Asegurado Ejemplar | Matrícula: 1234-XYZ | Vehículo: Modelo Turism 2024")

    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, 640, "1. Coberturas Principales y Garantías")
    c.setFont("Helvetica", 10)
    c.drawString(50, 620, "- Responsabilidad Civil Obligatoria y Voluntaria hasta 50.000.000 EUR.")
    c.drawString(50, 600, "- Daños Propios con franquicia pactada de 150 EUR por siniestro.")
    c.drawString(50, 580, "- Rotura e impacto en Lunas: Cobertura al 100% sin aplicación de franquicia.")
    c.drawString(50, 560, "- Robo e Incendio: Indemnización a valor de nuevo durante los primeros 2 años.")

    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, 520, "2. Vehículo de Sustitución")
    c.setFont("Helvetica", 10)
    c.drawString(50, 500, "En caso de inmovilización en taller superior a 24 horas por siniestro cubierto,")
    c.drawString(50, 485, "la aseguradora facilitará un vehículo de sustitución del Grupo B por un máximo de 7 días.")

    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, 445, "3. Resumen de Franquicias y Límites")
    c.setFont("Helvetica", 9)
    c.drawString(50, 425, "| Garantía | Franquicia | Límite Máximo |")
    c.drawString(50, 410, "| Daños por colisión | 150 EUR | Valor venal mejorado |")
    c.drawString(50, 395, "| Rotura de parabrisas | Sin franquicia | Valor de reposición original |")
    c.drawString(50, 380, "| Asistencia en viaje | Sin franquicia | Km 0 nacional e internacional |")

    c.showPage()
    c.save()


def generar_poliza_hogar(dest: Path) -> None:
    c = canvas.Canvas(str(dest), pagesize=letter)

    # Página 1
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, "PÓLIZA MULTIRRIESGO HOGAR INTEGRAL")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 710, "SECCIÓN I: DAÑOS MATERIALES Y CONTINENTE")
    c.setFont("Helvetica", 10)
    c.drawString(50, 670, "1.1 Incendio, explosión y caída de rayo.")
    c.drawString(50, 650, "Quedan amparados los daños directos causados al continente y contenido.")
    c.drawString(50, 620, "1.2 Daños por agua e inundación.")
    c.drawString(50, 600, "Cubre la rotura accidental de tuberías de distribución y desagüe de la vivienda.")
    c.drawString(50, 580, "No se cubren atascos ni daños derivados de falta continuada de mantenimiento.")
    c.showPage()

    # Página 2
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 750, "SECCIÓN II: RESPONSABILIDAD CIVIL Y FIANZAS")
    c.setFont("Helvetica", 10)
    c.drawString(50, 710, "2.1 Responsabilidad Civil Privada y Familiar hasta 300.000 EUR.")
    c.drawString(50, 690, "2.2 Cobertura de daños a colindantes por filtraciones originadas en el inmueble.")
    c.drawString(50, 660, "TABLA DE CAPITALES Y FRANQUICIAS:")
    c.drawString(50, 640, "| Concepto | Capital Asegurado | Franquicia |")
    c.drawString(50, 625, "| Continente | 180.000 EUR | 0 EUR |")
    c.drawString(50, 610, "| Contenido | 45.000 EUR | 0 EUR |")
    c.drawString(50, 595, "| Joyas y objetos de valor | 6.000 EUR | 100 EUR |")
    c.showPage()

    # Página 3
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 750, "SECCIÓN III: EXCLUSIONES GENERALES")
    c.setFont("Helvetica", 10)
    c.drawString(50, 710, "Quedan expresamente excluidos de todas las coberturas de la póliza:")
    c.drawString(50, 680, "- Hechos atribuibles a dolo o mala fe demostrada del asegurado.")
    c.drawString(50, 660, "- Fenómenos de la naturaleza consorciables asumidos por el Consorcio de Compensación.")
    c.drawString(50, 640, "- Desgaste paulatino, corrosión, humedad por condensación y vicios ocultos de construcción.")
    c.showPage()

    c.save()


def generar_archivo_corrupto(dest: Path) -> None:
    # Contiene magic bytes válidos pero cuerpo binario corrompido sin xref
    contenido = b"%PDF-1.4\n%%EOF_CORRUPTO_SIN_OBJETOS_NI_XREF_TRAILER_1234567890abcdef\x00\xff\xee"
    dest.write_bytes(contenido)


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    out_dir = repo_root / "samples"
    out_dir.mkdir(parents=True, exist_ok=True)

    generar_poliza_auto(out_dir / "poliza_basica_auto.pdf")
    generar_poliza_hogar(out_dir / "condiciones_generales_hogar.pdf")
    generar_archivo_corrupto(out_dir / "archivo_corrupto.pdf")
    print("Muestras generadas satisfactoriamente en samples/")


if __name__ == "__main__":
    main()
