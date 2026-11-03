"""Pruebas unitarias para generadores de embeddings y clientes LLM."""

import math

from app.llm.base import cosine_similarity, normalize_l2
from app.llm.factory import get_embedding_client, get_llm_client
from app.llm.fakes import FakeLLMClient, HashingEmbeddingClient
from app.llm.litellm_client import LiteLLMEmbeddingClient


def test_normalize_l2_truncado_y_norma_unitaria() -> None:
    """Verifica que normalize_l2 trunque a 768 y genere un vector de norma euclídea 1.0."""
    # Vector original de 1536 dimensiones (estilo text-embedding-3-small o Ada)
    vector_largo = [float(i % 10 + 1) for i in range(1536)]
    resultado = normalize_l2(vector_largo, target_dim=768)

    assert len(resultado) == 768
    norma = math.sqrt(sum(x * x for x in resultado))
    assert math.isclose(norma, 1.0, rel_tol=1e-5)


def test_hashing_embedding_dimension_y_norma() -> None:
    """Verifica que HashingEmbeddingClient devuelva vectores de 768d y norma 1.0."""
    client = HashingEmbeddingClient(dim=768)
    textos = [
        "Cobertura total ante colisión y daños a terceros.",
        "Franquicia deducible de 300 euros aplicable por siniestro.",
        "",  # Caso extremo texto vacío
    ]

    vectores = client.embed(textos)
    assert len(vectores) == 3

    for vec in vectores:
        assert len(vec) == 768
        norma = math.sqrt(sum(x * x for x in vec))
        assert math.isclose(norma, 1.0, rel_tol=1e-5)


def test_hashing_embedding_propiedades_semanticas_deterministas() -> None:
    """Verifica determinismo: textos idénticos -> 1.0; afines -> >0.3; disjuntos -> ~0.0."""
    client = HashingEmbeddingClient(dim=768)

    t1 = "El asegurado tiene derecho a coche de sustitución durante la reparación."
    t2 = "El asegurado tiene derecho a coche de sustitución durante la reparación."
    t_afin = "Vehículo de sustitución y asistencia para el asegurado en reparación."
    t_disjunto = "Meteorología tormentosa en alta mar sin relación con pólizas."

    v1, v2, v_afin, v_disj = client.embed([t1, t2, t_afin, t_disjunto])

    # 1. Textos idénticos
    sim_identica = cosine_similarity(v1, v2)
    assert math.isclose(sim_identica, 1.0, rel_tol=1e-5)

    # 2. Textos afines con términos compartidos
    sim_afin = cosine_similarity(v1, v_afin)
    assert sim_afin > 0.30

    # 3. Textos completamente disjuntos
    sim_disj = cosine_similarity(v1, v_disj)
    assert abs(sim_disj) < 0.25


def test_factorias_llm_y_embeddings() -> None:
    """Verifica la inicialización mediante las fábricas get_embedding_client y get_llm_client."""
    emb_fake = get_embedding_client("fake")
    assert isinstance(emb_fake, HashingEmbeddingClient)
    assert emb_fake.dim == 768

    llm_fake = get_llm_client("fake")
    assert isinstance(llm_fake, FakeLLMClient)
    respuesta = llm_fake.generate([{"role": "user", "content": "¿Cubre granizo?"}])
    assert "Pampero FAKE response" in respuesta


def test_litellm_embedding_fallback_seguro() -> None:
    """Verifica que LiteLLMEmbeddingClient recurra al cliente fake si no hay conexión externa."""
    # Inicializado con modelo inexistente o sin api keys
    cliente_litellm = LiteLLMEmbeddingClient(model="invalido/modelo-no-existente", dim=768)
    vectores = cliente_litellm.embed(["Prueba de fallback sin red"])

    assert len(vectores) == 1
    assert len(vectores[0]) == 768
    norma = math.sqrt(sum(x * x for x in vectores[0]))
    assert math.isclose(norma, 1.0, rel_tol=1e-5)
