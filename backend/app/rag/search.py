from sqlalchemy import text

from app.rag.embeddings import embed_texts

SQL = text("""
WITH vec AS (
  SELECT c.id, 1 - (c.embedding <=> CAST(:qv AS vector)) AS sim,
         ROW_NUMBER() OVER (ORDER BY c.embedding <=> CAST(:qv AS vector)) AS rnk
  FROM document_chunks c JOIN documents d ON d.id = c.document_id
  WHERE c.org_id = :org AND d.status = 'ready'
    AND (d.access_roles IS NULL OR jsonb_exists(d.access_roles, CAST(:role AS text)))
    AND (CAST(:cat AS text) IS NULL OR d.category = CAST(:cat AS text))
  ORDER BY c.embedding <=> CAST(:qv AS vector) LIMIT 20),
fts AS (
  SELECT c.id, ts_rank_cd(to_tsvector('english', c.content), q) AS fr,
         ROW_NUMBER() OVER (ORDER BY ts_rank_cd(to_tsvector('english', c.content), q) DESC) AS rnk
  FROM document_chunks c JOIN documents d ON d.id = c.document_id,
       websearch_to_tsquery('english', CAST(:q AS text)) q
  WHERE c.org_id = :org AND d.status = 'ready'
    AND (d.access_roles IS NULL OR jsonb_exists(d.access_roles, CAST(:role AS text)))
    AND (CAST(:cat AS text) IS NULL OR d.category = CAST(:cat AS text))
    AND to_tsvector('english', c.content) @@ q
  ORDER BY fr DESC LIMIT 20)
SELECT c.id, c.document_id, d.filename, c.idx, c.content,
       COALESCE(v.sim, 0) AS sim, COALESCE(f.fr, 0) AS fts_rank,
       COALESCE(1.0/(60 + v.rnk), 0) + COALESCE(1.0/(60 + f.rnk), 0) AS score
FROM document_chunks c JOIN documents d ON d.id = c.document_id
LEFT JOIN vec v ON v.id = c.id LEFT JOIN fts f ON f.id = c.id
WHERE v.id IS NOT NULL OR f.id IS NOT NULL
ORDER BY score DESC LIMIT :k
""")


def hybrid_search(db, org_id, role, query, k=5, category=None, min_sim=0.1):
    """Hybrid (pgvector + FTS) with RRF fusion. ALWAYS filtered by org and document role access."""
    qv = "[" + ",".join(f"{x:.6f}" for x in embed_texts([query], is_query=True)[0]) + "]"
    rows = db.execute(SQL, {"qv": qv, "org": org_id, "role": role, "cat": category, "q": query, "k": k * 2}).mappings().all()
    out = []
    for r in rows:
        if r["fts_rank"] > 0 or r["sim"] >= min_sim:  # evidence filter
            out.append({"chunk_id": str(r["id"]), "document_id": str(r["document_id"]), "filename": r["filename"],
                        "chunk_index": r["idx"], "content": r["content"], "similarity": round(float(r["sim"]), 4),
                        "fts_rank": round(float(r["fts_rank"]), 4), "score": round(float(r["score"]), 5),
                        "citation": f"{r['filename']}#chunk-{r['idx']}"})
    return out[:k]
