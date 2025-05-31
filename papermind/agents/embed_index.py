import os, json, uuid, hashlib
from typing import Dict
from chromadb import PersistentClient
from papermind.providers import embedder
from papermind.agents.chunk_pdf import detect_chunks

CHECKSUM_FILE = "papermind/store/processed_checksums.json"
BATCH = 100

def _load() -> Dict[str, str]:
    if os.path.exists(CHECKSUM_FILE):
        try:
            with open(CHECKSUM_FILE) as f:
                return json.load(f)
        except:
            return {}
    return {}

def _save(d: Dict[str, str]):
    os.makedirs(os.path.dirname(CHECKSUM_FILE), exist_ok=True)
    with open(CHECKSUM_FILE, "w") as f:
        json.dump(d, f, indent=2)

def _md5(p: str) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(4096), b""):
            h.update(c)
    return h.hexdigest()

async def upsert(pdf: str):
    os.makedirs("papermind/store", exist_ok=True)
    chks = _load()
    md5 = _md5(pdf)
    if chks.get(os.path.basename(pdf)) == md5:
        return
    coll = PersistentClient(path="papermind/store").get_or_create_collection("chunks")
    items = detect_chunks(pdf)
    if not items:
        return
    texts = [f"{c['header']} {c['body']}" for c in items]
    embeds = []
    for i in range(0, len(texts), BATCH):
        embeds.extend(await embedder.embed(texts[i:i + BATCH]))
    ids = [str(uuid.uuid4()) for _ in items]
    docs = [json.dumps(c, ensure_ascii=False) for c in items]
    metas = [{"header": c["header"], "page": c["page"]} for c in items]
    coll.add(ids=ids, embeddings=embeds, documents=docs, metadatas=metas)
    chks[os.path.basename(pdf)] = md5
    _save(chks)
