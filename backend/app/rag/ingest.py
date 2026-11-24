import io
import re
import uuid

from sqlalchemy import delete

from app.models import Document, DocumentChunk
from app.rag.embeddings import embed_texts


def extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        from pypdf import PdfReader
        return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)
    if name.endswith(".docx"):
        from docx import Document as Docx
        return "\n".join(p.text for p in Docx(io.BytesIO(data)).paragraphs)
    if name.endswith((".txt", ".md", ".csv")):
        return data.decode("utf-8", errors="ignore")
    raise ValueError("Unsupported file type (use PDF, DOCX, TXT or MD)")


def clean(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def chunk_text(text: str, size=160, step=130) -> list[str]:
    words = text.split()
    return [" ".join(words[i:i + size]) for i in range(0, max(len(words), 1), step) if words[i:i + size]]


def ingest_document(db, doc: Document, data: bytes):
    """Extract -> clean -> chunk -> embed -> store. Re-indexing deletes old chunks first."""
    try:
        db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc.id))
        text = clean(extract_text(doc.filename, data))
        if not text:
            raise ValueError("No extractable text")
        chunks = chunk_text(text)
        vecs = embed_texts(chunks)
        for i, (c, v) in enumerate(zip(chunks, vecs)):
            db.add(DocumentChunk(id=uuid.uuid4(), org_id=doc.org_id, document_id=doc.id, idx=i, content=c,
                                 meta={"filename": doc.filename, "category": doc.category, "chunk": i},
                                 embedding=v))
        doc.chunk_count, doc.status, doc.error = len(chunks), "ready", None
    except Exception as e:
        doc.status, doc.error = "failed", str(e)[:400]
