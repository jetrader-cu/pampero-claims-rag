"""Script de inicialización y siembra (seed) de datos de demostración.

Crea los tenants 'pampero-norte' y 'pampero-sur', sus usuarios respectivos con API Keys
fijas de demo y procesa los documentos PDF oficiales de cada tenant para que queden
completamente indexados y listos para consulta RAG.
"""

import asyncio
import hashlib
from pathlib import Path
import sys
import uuid

# Asegurar importación de app desde backend
repo_root = Path(__file__).resolve().parent.parent
backend_path = repo_root / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from sqlalchemy import select  # noqa: E402
from app.core.security import hash_api_key  # noqa: E402
from app.db.engine import async_session_maker  # noqa: E402
from app.db.models import Document, IngestionJob, Tenant, User  # noqa: E402
from app.db.tenant import set_tenant_context  # noqa: E402
from app.ingest.pipeline import run_ingestion  # noqa: E402
from app.ingest.storage import get_storage  # noqa: E402
from app.ingest.validation import validate_pdf_bytes  # noqa: E402

API_KEY_NORTE = "pampero_key_demo_norte"
API_KEY_SUR = "pampero_key_demo_sur"


async def sembrar_tenant(
    slug: str,
    nombre: str,
    email_usuario: str,
    api_key: str,
    carpeta_samples: Path,
) -> tuple[Tenant, User, list[str]]:
    """Crea o recupera un tenant, su usuario y procesa sus documentos."""
    storage = get_storage()
    docs_procesados: list[str] = []

    async with async_session_maker() as session:
        # 1. Tenant
        stmt_tenant = select(Tenant).where(Tenant.slug == slug)
        tenant = await session.scalar(stmt_tenant)
        if tenant is None:
            tenant = Tenant(
                id=uuid.uuid4(),
                slug=slug,
                name=nombre,
            )
            session.add(tenant)
            await session.commit()
            print(f" [+] Tenant creado: {nombre} ({slug}) -> {tenant.id}")
        else:
            print(f" [i] Tenant existente: {nombre} ({slug}) -> {tenant.id}")

        tenant_id = tenant.id

        # 2. Usuario
        await set_tenant_context(session, tenant_id)
        stmt_user = select(User).where(User.tenant_id == tenant_id, User.email == email_usuario)
        user = await session.scalar(stmt_user)
        if user is None:
            user = User(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                email=email_usuario,
                api_key_hash=hash_api_key(api_key),
                api_key_prefix=api_key[:8],
            )
            session.add(user)
            await session.commit()
            print(f" [+] Usuario creado: {email_usuario} con API Key: {api_key}")
        else:
            print(f" [i] Usuario existente: {email_usuario}")

        # 3. Procesar documentos de muestra
        archivos = sorted(list(carpeta_samples.glob("*.pdf")))
        if not archivos:
            print(f" [!] Alerta: no se encontraron PDFs en {carpeta_samples}")

        for pdf_path in archivos:
            content = pdf_path.read_bytes()
            sha256 = hashlib.sha256(content).digest()

            # Validar integridad del PDF
            try:
                page_count = validate_pdf_bytes(content)
            except Exception as e:
                print(f" [!] Omitiendo {pdf_path.name} por fallo de validación inicial: {e}")
                continue

            # Asegurar contexto RLS para esta iteración
            await set_tenant_context(session, tenant_id)

            # Verificar si ya existe en el tenant
            stmt_doc = select(Document).where(
                Document.tenant_id == tenant_id,
                Document.sha256 == sha256,
            )
            doc_existente = await session.scalar(stmt_doc)

            if doc_existente is not None and doc_existente.status == "ready":
                print(f" [i] Documento ya indexado: {pdf_path.name} (chunks: {doc_existente.chunk_count})")
                docs_procesados.append(f"{pdf_path.name} (existente, {doc_existente.chunk_count} chunks)")
                continue

            doc_id = uuid.uuid4()
            job_id = uuid.uuid4()
            storage_key = await storage.save(tenant_id, doc_id, content)

            # Asegurar contexto RLS antes de insertar
            await set_tenant_context(session, tenant_id)

            doc = Document(
                id=doc_id,
                tenant_id=tenant_id,
                uploaded_by=user.id,
                filename=pdf_path.name,
                size_bytes=len(content),
                page_count=page_count,
                sha256=sha256,
                storage_key=storage_key,
                status="queued",
            )
            job = IngestionJob(
                id=job_id,
                tenant_id=tenant_id,
                document_id=doc_id,
                status="queued",
                max_attempts=5,
            )
            session.add(doc)
            session.add(job)
            await session.commit()

            print(f" [>] Ingestando {pdf_path.name}...")
            # Ejecutar pipeline síncronamente en proceso para asegurar indexación inmediata
            try:
                run_ingestion(job_id)
            except Exception as e:
                print(f" [!] Error en ingesta de {pdf_path.name}: {e}")

            # Recargar documento para confirmar estado
            async with async_session_maker() as check_session:
                await set_tenant_context(check_session, tenant_id)
                doc_recargado = await check_session.get(Document, doc_id)
                chunks_num = doc_recargado.chunk_count if doc_recargado else 0
                estado = doc_recargado.status if doc_recargado else "desconocido"
                print(f" [✓] {pdf_path.name} -> estado: {estado}, chunks: {chunks_num}")
                docs_procesados.append(f"{pdf_path.name} ({estado}, {chunks_num} chunks)")

    return tenant, user, docs_procesados


async def main_async() -> None:
    print("=" * 70)
    print("PAMPERO CLAIMS ASSISTANT — INICIALIZACIÓN DE DATOS (SEED)")
    print("=" * 70)

    # 1. Asegurar generación de muestras si no existen
    samples_dir = repo_root / "samples"
    norte_samples = samples_dir / "norte"
    sur_samples = samples_dir / "sur"

    if not norte_samples.exists() or not sur_samples.exists():
        print("Muestras no detectadas. Ejecutando scripts/generate_samples.py...")
        from scripts.generate_samples import main as gen_samples
        gen_samples()

    # 2. Sembrar Tenant Norte
    print("\n--- Aprovisionando Pampero Norte ---")
    tenant_norte, user_norte, docs_norte = await sembrar_tenant(
        slug="pampero-norte",
        nombre="Pampero Norte Seguros",
        email_usuario="ajustador-norte@pampero.local",
        api_key=API_KEY_NORTE,
        carpeta_samples=norte_samples,
    )

    # 3. Sembrar Tenant Sur
    print("\n--- Aprovisionando Pampero Sur ---")
    tenant_sur, user_sur, docs_sur = await sembrar_tenant(
        slug="pampero-sur",
        nombre="Pampero Sur Seguros",
        email_usuario="ajustador-sur@pampero.local",
        api_key=API_KEY_SUR,
        carpeta_samples=sur_samples,
    )

    print("\n" + "=" * 70)
    print("RESUMEN DE SIEMBRA COMPLETA")
    print("=" * 70)
    print(f"Tenant Norte: {tenant_norte.name} (ID: {tenant_norte.id})")
    print(f"  Usuario:   {user_norte.email}")
    print(f"  API Key:   {API_KEY_NORTE}")
    print(f"  Documentos ({len(docs_norte)}):")
    for d in docs_norte:
        print(f"    - {d}")

    print(f"\nTenant Sur:   {tenant_sur.name} (ID: {tenant_sur.id})")
    print(f"  Usuario:   {user_sur.email}")
    print(f"  API Key:   {API_KEY_SUR}")
    print(f"  Documentos ({len(docs_sur)}):")
    for d in docs_sur:
        print(f"    - {d}")
    print("=" * 70)


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
