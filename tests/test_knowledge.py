"""Tests for knowledge base."""

import pytest
from pathlib import Path

from unittest.mock import Mock
from termmind.knowledge.rag import Document, VectorStore, DocumentLoader, RAGPipeline


class TestDocument:
    def test_creation(self):
        doc = Document("Hello world")
        assert doc.content == "Hello world"
        assert doc.metadata == {}
    
    def test_chunking(self):
        doc = Document("a" * 2000)
        chunks = doc.chunk(chunk_size=1000, overlap=100)
        assert len(chunks) > 1
        assert all(len(c.content) <= 1000 for c in chunks)
    
    def test_metadata(self):
        doc = Document("test", {"source": "file.md"})
        assert doc.metadata["source"] == "file.md"


class TestVectorStore:
    def test_add_and_get(self):
        store = VectorStore()
        doc = Document("Python is great for AI")
        store.add("1", doc)
        assert store.get("1") == doc
    
    def test_search(self):
        store = VectorStore()
        store.add("1", Document("Python is great for AI"))
        store.add("2", Document("JavaScript is for web"))
        store.add("3", Document("Rust is for systems"))
        
        results = store.search("Python AI", top_k=5)
        assert len(results) > 0
    
    def test_delete(self):
        store = VectorStore()
        store.add("1", Document("test"))
        assert store.delete("1")
        assert not store.delete("1")
    
    def test_count(self):
        store = VectorStore()
        assert store.count() == 0
        store.add("1", Document("test"))
        assert store.count() == 1
    
    def test_save_load(self, tmp_path):
        store = VectorStore("test_collection")
        store.add("1", Document("hello", {"source": "a"}))
        
        path = tmp_path / "store.json"
        store.save(str(path))
        
        store2 = VectorStore()
        store2.load(str(path))
        assert store2.count() == 1
        assert store2.collection_name == "test_collection"


class TestDocumentLoader:
    def test_from_text(self):
        doc = DocumentLoader.from_text("Hello", {"type": "test"})
        assert doc.content == "Hello"
        assert doc.metadata["type"] == "test"
    
    def test_from_directory(self, tmp_path):
        (tmp_path / "a.md").write_text("hello")
        (tmp_path / "b.md").write_text("world")
        
        docs = DocumentLoader.from_directory(str(tmp_path), "*.md")
        assert len(docs) == 2


class TestRAGPipeline:
    def test_query(self):
        store = VectorStore()
        store.add("1", Document("Python is a programming language"))
        
        client = Mock()
        client.chat = Mock(return_value="Python is a programming language.")
        
        rag = RAGPipeline(store, client)
        answer = rag.query("What is Python?")
        assert "Python" in answer
    
    def test_query_no_docs(self):
        store = VectorStore()
        client = Mock()
        client.chat = Mock(return_value="I don't know.")
        
        rag = RAGPipeline(store, client)
        answer = rag.query("What is Python?")
        assert "I don't know" in answer
    
    def test_add_documents(self):
        store = VectorStore()
        client = Mock()
        rag = RAGPipeline(store, client)
        
        docs = [Document("a" * 2000)]
        rag.add_documents(docs)
        assert store.count() > 0
