"""Knowledge base with RAG pipeline."""

from pathlib import Path
from typing import Any, Optional, Callable

from termmind.api import APIClient

def dot_product(v1: list[float], v2: list[float]) -> float:
    return sum(x * y for x, y in zip(v1, v2))

def magnitude(v: list[float]) -> float:
    return sum(x * x for x in v) ** 0.5

def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    m1 = magnitude(v1)
    m2 = magnitude(v2)
    if m1 == 0.0 or m2 == 0.0:
        return 0.0
    return dot_product(v1, v2) / (m1 * m2)


class Document:
    """Represents a document in the knowledge base."""

    def __init__(self, content: str, metadata: Optional[dict[str, Any]] = None) -> None:
        self.content = content
        self.metadata = metadata or {}
        self.embedding: Optional[list[float]] = None

    def chunk(self, chunk_size: int = 1000, overlap: int = 100) -> list["Document"]:
        """Split document into overlapping chunks."""
        chunks = []
        start = 0
        while start < len(self.content):
            end = min(start + chunk_size, len(self.content))
            chunk_content = self.content[start:end]
            meta = {**self.metadata, "chunk_start": start, "chunk_end": end}
            chunks.append(Document(chunk_content, meta))
            start = end - overlap if end < len(self.content) else end
        return chunks

    def __repr__(self) -> str:
        return f"Document({len(self.content)} chars, metadata={self.metadata})"


class VectorStore:
    """Vector store with semantic embeddings and term-overlap fallbacks."""

    def __init__(self, collection_name: str = "termmind_kb") -> None:
        self.collection_name = collection_name
        self._documents: dict[str, Document] = {}

    def add(self, doc_id: str, document: Document, embed_fn: Optional[Callable[[str], list[float]]] = None) -> None:
        """Add a document to the store, optionally embedding it."""
        if embed_fn and not document.embedding:
            try:
                document.embedding = embed_fn(document.content)
            except Exception:
                pass
        self._documents[doc_id] = document

    def search(self, query: str, top_k: int = 5, embed_fn: Optional[Callable[[str], list[float]]] = None) -> list[Document]:
        """Search for relevant documents using semantic embeddings or term matching fallback."""
        query_embedding = None
        if embed_fn:
            try:
                query_embedding = embed_fn(query)
            except Exception:
                pass

        scored = []
        use_semantic = isinstance(query_embedding, list) and len(query_embedding) > 0
        if use_semantic:
            has_doc_embeddings = any(isinstance(doc.embedding, list) and len(doc.embedding) > 0 for doc in self._documents.values())
            if not has_doc_embeddings:
                use_semantic = False

        if use_semantic:
            for doc in self._documents.values():
                if doc.embedding and len(doc.embedding) == len(query_embedding):
                    score = cosine_similarity(query_embedding, doc.embedding)
                else:
                    query_terms = set(query.lower().split())
                    doc_terms = set(doc.content.lower().split())
                    if not query_terms or not doc_terms:
                        score = 0.0
                    else:
                        score = len(query_terms & doc_terms) / len(query_terms | doc_terms)
                scored.append((score, doc))
        else:
            query_terms = set(query.lower().split())
            for doc in self._documents.values():
                doc_terms = set(doc.content.lower().split())
                score = len(query_terms & doc_terms)
                if score > 0:
                    scored.append((float(score), doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for score, doc in scored if score > 0.0][:top_k]

    def get(self, doc_id: str) -> Optional[Document]:
        """Get a document by ID."""
        return self._documents.get(doc_id)

    def list(self) -> list[str]:
        """List all document IDs."""
        return list(self._documents.keys())

    def delete(self, doc_id: str) -> bool:
        """Delete a document."""
        if doc_id in self._documents:
            del self._documents[doc_id]
            return True
        return False

    def count(self) -> int:
        """Count documents."""
        return len(self._documents)

    def save(self, path: str) -> None:
        """Save store to JSON."""
        import json
        data = {
            "collection": self.collection_name,
            "documents": {
                k: {"content": v.content, "metadata": v.metadata, "embedding": v.embedding}
                for k, v in self._documents.items()
            }
        }
        Path(path).write_text(json.dumps(data, indent=2))

    def load(self, path: str) -> None:
        """Load store from JSON."""
        import json
        data = json.loads(Path(path).read_text())
        self.collection_name = data.get("collection", self.collection_name)
        self._documents = {}
        for k, v in data.get("documents", {}).items():
            doc = Document(v["content"], v["metadata"])
            doc.embedding = v.get("embedding")
            self._documents[k] = doc


class DocumentLoader:
    """Load documents from various sources."""

    @staticmethod
    def from_file(path: str) -> Document:
        """Load a document from a file."""
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        content = file_path.read_text(encoding="utf-8", errors="ignore")
        return Document(content, {"source": path, "type": file_path.suffix})

    @staticmethod
    def from_text(text: str, metadata: Optional[dict[str, Any]] = None) -> Document:
        """Create a document from raw text."""
        return Document(text, metadata)

    @staticmethod
    def from_directory(dir_path: str, pattern: str = "*.md") -> list[Document]:
        """Load all matching files from a directory."""
        docs = []
        path = Path(dir_path)
        if path.exists():
            for file_path in path.rglob(pattern):
                try:
                    docs.append(DocumentLoader.from_file(str(file_path)))
                except Exception:
                    continue
        return docs


class RAGPipeline:
    """Retrieval Augmented Generation pipeline.

    Usage:
        store = VectorStore()
        rag = RAGPipeline(store, client)
        rag.add_documents(docs)
        answer = rag.query("What is RAG?")
    """

    def __init__(self, vector_store: VectorStore, client: APIClient) -> None:
        self.vector_store = vector_store
        self.client = client

    def query(self, question: str, top_k: int = 5) -> str:
        """Query using RAG."""
        relevant_docs = self.vector_store.search(question, top_k=top_k, embed_fn=self.client.embed)

        if not relevant_docs:
            return self.client.chat([{"role": "user", "content": question}])

        context = "\n\n".join([
            f"Document {i+1}:\n{doc.content[:1000]}"
            for i, doc in enumerate(relevant_docs)
        ])

        prompt = f"""Use the following context to answer the question.

Context:
{context}

Question: {question}

Answer:"""

        return self.client.chat([{"role": "user", "content": prompt}])

    def add_documents(self, documents: list[Document]) -> None:
        """Add documents to the RAG pipeline."""
        for i, doc in enumerate(documents):
            chunks = doc.chunk()
            for j, chunk in enumerate(chunks):
                self.vector_store.add(f"doc_{i}_chunk_{j}", chunk, embed_fn=self.client.embed)


__all__ = ["Document", "VectorStore", "DocumentLoader", "RAGPipeline"]
