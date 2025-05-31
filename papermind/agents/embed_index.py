from chromadb import Client
from papermind.providers import embedder # Corrected import path
from papermind.agents.chunk_pdf import detect_chunks # Corrected import path
import uuid
import json
import os # os was imported but not used in the snippet, will keep it for now as it might be used later.

async def upsert(pdf_path: str): # Added async keyword
    # Ensure the 'store' directory exists, as chromadb.Client(path="store") might need it.
    os.makedirs("papermind/store", exist_ok=True)
    coll = Client(path="papermind/store").get_or_create_collection("chunks") # Corrected path

    chunks_data = detect_chunks(pdf_path) # Call detect_chunks

    if not chunks_data:
        print(f"No chunks detected in {pdf_path}")
        return

    texts_to_embed = [chk["header"] + " " + chk["body"] for chk in chunks_data]

    if not texts_to_embed:
        print(f"No text content to embed in {pdf_path}")
        return

    embeddings = await embedder.embed(texts_to_embed) # Added await

    ids = [str(uuid.uuid4()) for _ in chunks_data]
    documents = [json.dumps(chk, ensure_ascii=False) for chk in chunks_data]
    metadatas = [{"header": chk["header"], "page": chk["page"]} for chk in chunks_data]

    coll.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
    print(f"Successfully processed and indexed {pdf_path}")
