"""Knowledge base with RAG pipeline."""

from pathlib import Path
from typing import Any, Optional

from termmind.api import APIClient


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
    """Simple vector store with TF-IDF-like scoring.

    In production, use ChromaDB, Qdrant, or Pinecone.
    """

    def __init__(self, collection_name: str = "termmind_kb") -> None:
        self.collection_name = collection_name
        self._documents: dict[str, Document] = {}

    def add(self, doc_id: str, document: Document) -> None:
        """Add a document to the store."""
        self._documents[doc_id] = document

    def search(self, query: str, top_k: int = 5) -> list[Document]:
        """Search for relevant documents using simple term matching."""
        query_terms = set(query.lower().split())
        scored = []

        for doc in self._documents.values():
            doc_terms = set(doc.content.lower().split())
            score = len(query_terms & doc_terms)
            if score > 0:
                scored.append((score, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored[:top_k]]

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
                k: {"content": v.content, "metadata": v.metadata}
                for k, v in self._documents.items()
            }
        }
        Path(path).write_text(json.dumps(data, indent=2))

    def load(self, path: str) -> None:
        """Load store from JSON."""
        import json
        data = json.loads(Path(path).read_text())
        self.collection_name = data.get("collection", self.collection_name)
        self._documents = {
            k: Document(v["content"], v["metadata"])
            for k, v in data.get("documents", {}).items()
        }


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
        relevant_docs = self.vector_store.search(question, top_k=top_k)

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
                self.vector_store.add(f"doc_{i}_chunk_{j}", chunk)


__all__ = ["Document", "VectorStore", "DocumentLoader", "RAGPipeline"]
