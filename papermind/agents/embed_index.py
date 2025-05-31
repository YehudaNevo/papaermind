import os, json, uuid, hashlib
from typing import Dict
from chromadb import PersistentClient # User updated this
from papermind.providers import embedder
from papermind.agents.chunk_pdf import detect_chunks

CHECKSUM_FILE = "papermind/store/processed_checksums.json"
BATCH = 100 # User defined batch size

def _load() -> Dict[str, str]:
    if os.path.exists(CHECKSUM_FILE):
        try:
            with open(CHECKSUM_FILE) as f:
                return json.load(f)
        except: # Catch all for robustness
            return {}
    return {}

def _save(d: Dict[str, str]):
    os.makedirs(os.path.dirname(CHECKSUM_FILE), exist_ok=True)
    with open(CHECKSUM_FILE, "w") as f:
        json.dump(d, f, indent=2)

def _md5(p: str) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        for c_chunk in iter(lambda: f.read(4096), b""): # Renamed c to c_chunk
            h.update(c_chunk)
    return h.hexdigest()

async def upsert(pdf: str): # pdf is path string
    os.makedirs("papermind/store", exist_ok=True)
    chks = _load()
    md5 = _md5(pdf)
    # User's logic for checking checksum
    if chks.get(os.path.basename(pdf)) == md5:
        print(f"Skipping {os.path.basename(pdf)}, checksum matches.") # Added print
        return

    # User updated to PersistentClient
    coll = PersistentClient(path="papermind/store").get_or_create_collection("chunks")
    items = detect_chunks(pdf)
    if not items:
        print(f"No chunks detected in {pdf}.") # Added print
        return

    texts = [f"{c['header']} {c['body']}" for c in items]
    embeds = []
    for i in range(0, len(texts), BATCH): # Batching logic from user
        embeds.extend(await embedder.embed(texts[i:i + BATCH]))

    ids = [str(uuid.uuid4()) for _ in items]
    docs = [json.dumps(c, ensure_ascii=False) for c in items]
    metas = [{"header": c["header"], "page": c["page"]} for c in items]

    coll.add(ids=ids, embeddings=embeds, documents=docs, metadatas=metas)
    chks[os.path.basename(pdf)] = md5 # Update checksum map
    _save(chks)
    print(f"Successfully indexed {os.path.basename(pdf)}.") # Added print
