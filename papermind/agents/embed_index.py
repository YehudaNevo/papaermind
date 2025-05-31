from chromadb import Client
from papermind.providers import embedder
from papermind.agents.chunk_pdf import detect_chunks
import uuid
import json
import os
import hashlib

CHECKSUM_FILE_PATH = "papermind/store/processed_checksums.json"
EMBED_BATCH_SIZE = 100

def load_checksums() -> Dict[str, str]:
    if os.path.exists(CHECKSUM_FILE_PATH):
        try:
            with open(CHECKSUM_FILE_PATH, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def save_checksums(checksums: Dict[str, str]):
    os.makedirs(os.path.dirname(CHECKSUM_FILE_PATH), exist_ok=True)
    with open(CHECKSUM_FILE_PATH, "w") as f:
        json.dump(checksums, f, indent=2)

def calculate_md5(filepath: str) -> str:
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

async def upsert(pdf_path: str):
    os.makedirs("papermind/store", exist_ok=True)

    pdf_checksum = calculate_md5(pdf_path)
    processed_checksums = load_checksums()

    if processed_checksums.get(os.path.basename(pdf_path)) == pdf_checksum:
        print(f"Skipping '{pdf_path}', checksum matches previously processed version.")
        return

    coll = Client(path="papermind/store").get_or_create_collection("chunks")

    chunks_data = detect_chunks(pdf_path)

    if not chunks_data:
        print(f"No chunks detected in {pdf_path}")
        return

    texts_to_embed = [chk["header"] + " " + chk["body"] for chk in chunks_data]

    if not texts_to_embed:
        print(f"No text content to embed in {pdf_path}")
        return

    all_embeddings = []
    for i in range(0, len(texts_to_embed), EMBED_BATCH_SIZE):
        batch_texts = texts_to_embed[i:i + EMBED_BATCH_SIZE]
        batch_embeddings = await embedder.embed(batch_texts)
        all_embeddings.extend(batch_embeddings)
        print(f"Embedded batch {i//EMBED_BATCH_SIZE + 1}/{(len(texts_to_embed) - 1)//EMBED_BATCH_SIZE + 1} for {pdf_path}")


    if len(all_embeddings) != len(chunks_data):
        print(f"Error: Number of embeddings ({len(all_embeddings)}) does not match number of chunks ({len(chunks_data)}) for {pdf_path}.")
        return

    ids = [str(uuid.uuid4()) for _ in chunks_data]
    documents = [json.dumps(chk, ensure_ascii=False) for chk in chunks_data]
    metadatas = [{"header": chk["header"], "page": chk["page"]} for chk in chunks_data]

    coll.add(ids=ids, embeddings=all_embeddings, documents=documents, metadatas=metadatas)

    processed_checksums[os.path.basename(pdf_path)] = pdf_checksum
    save_checksums(processed_checksums)

    print(f"Successfully processed and indexed {pdf_path}")
