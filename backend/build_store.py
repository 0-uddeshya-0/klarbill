# backend/build_store.py

import os, json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

base = os.path.dirname(__file__)
data_dir = os.path.join(base, "data")
vs_dir   = os.path.join(base, "vectorstore")
os.makedirs(vs_dir, exist_ok=True)

# 1) Load your JSON
with open(os.path.join(data_dir, "knowledge_base.json"), "r", encoding="utf-8") as f:
    kb = json.load(f)["utility_invoice_queries"]

# 2) Flatten into Q–A strings
docs = []
for section in kb.values():
    for entry in section:
        q = entry["input"].strip()
        a = entry["response"].strip()
        docs.append(f"Q: {q} A: {a}")

# 3) Embed questions (or Q+A) into vectors
embed_model = SentenceTransformer("all-MiniLM-L6-v2")
embeddings = embed_model.encode(docs, normalize_embeddings=True)

# 4) Build an Inner-Product FAISS index
dim = embeddings.shape[1]
index = faiss.IndexFlatIP(dim)
index.add(np.array(embeddings).astype("float32"))

# 5) Persist index + docs
faiss.write_index(index, os.path.join(vs_dir, "kb.faiss"))
with open(os.path.join(vs_dir, "kb_docs.txt"), "w", encoding="utf-8") as f:
    for doc in docs:
        f.write(doc.replace("\n", " ") + "\n")

print("✅ Vector store built in", vs_dir)
