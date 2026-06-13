"""Unit tests for knowledge base embeddings and cosine similarity search."""

import pytest
from termmind.knowledge.rag import (
    Document,
    VectorStore,
    dot_product,
    magnitude,
    cosine_similarity,
)


def test_cosine_similarity_math():
    """Test standard cosine similarity math and corner cases."""
    v1 = [1.0, 0.0, 0.0]
    v2 = [0.0, 1.0, 0.0]
    # Orthogonal vectors should have 0 similarity
    assert abs(cosine_similarity(v1, v2)) < 1e-6

    # Identical vectors should have 1 similarity
    assert abs(cosine_similarity(v1, v1) - 1.0) < 1e-6

    # Parallel opposite vectors should have -1 similarity
    v3 = [-1.0, 0.0, 0.0]
    assert abs(cosine_similarity(v1, v3) - (-1.0)) < 1e-6

    # Handle zero vectors gracefully
    zero = [0.0, 0.0, 0.0]
    assert cosine_similarity(v1, zero) == 0.0


def test_vector_store_embedding_search():
    """Test that VectorStore successfully retrieves documents using embeddings."""
    store = VectorStore(collection_name="test_embeddings")

    # Define documents with embeddings
    doc1 = Document("Python coding assistant", {"source": "python.txt"})
    doc1.embedding = [1.0, 0.0, 0.0]

    doc2 = Document("Terminal chat application", {"source": "terminal.txt"})
    doc2.embedding = [0.0, 1.0, 0.0]

    store.add("doc1", doc1)
    store.add("doc2", doc2)

    # Query matching doc1
    def mock_embed_doc1(text):
        return [1.0, 0.0, 0.0]

    results1 = store.search("Python", top_k=1, embed_fn=mock_embed_doc1)
    assert len(results1) == 1
    assert results1[0].content == "Python coding assistant"

    # Query matching doc2
    def mock_embed_doc2(text):
        return [0.0, 1.0, 0.0]

    results2 = store.search("terminal", top_k=1, embed_fn=mock_embed_doc2)
    assert len(results2) == 1
    assert results2[0].content == "Terminal chat application"


def test_vector_store_search_fallback():
    """Test that VectorStore falls back to term overlap when embeddings are missing."""
    store = VectorStore(collection_name="test_fallback")

    # doc1 has no embedding, doc2 has embedding
    doc1 = Document("Python coding assistant", {"source": "python.txt"})
    
    doc2 = Document("Terminal chat application", {"source": "terminal.txt"})
    doc2.embedding = [0.0, 1.0, 0.0]

    store.add("doc1", doc1)
    store.add("doc2", doc2)

    # Search with term matching (no embed_fn provided)
    results = store.search("Python assistant", top_k=2)
    assert len(results) >= 1
    assert results[0].content == "Python coding assistant"

    # Search with embed_fn but doc1 doesn't have an embedding - should fallback
    def mock_embed(text):
        return [1.0, 0.0, 0.0]

    results_fallback = store.search("Python assistant", top_k=2, embed_fn=mock_embed)
    assert len(results_fallback) >= 1
    # doc1 should match via term overlap fallback
    assert results_fallback[0].content == "Python coding assistant"
