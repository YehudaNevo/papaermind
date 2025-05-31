import asyncio
import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
import os
import argparse
import json # Required for SSE JSON data if we switch to that format

# User provided: ensure .env is loaded relative to this file's directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

from papermind.agents.ask_graph import rag_app
from papermind.agents.embed_index import upsert as upsert_pdf_chunks
# User updated to PersistentClient, renamed here to avoid conflict if ChromaClient was used elsewhere
from chromadb import PersistentClient as ChromaServicePersistentClient
from papermind.tests.create_dummy import create_dummy_pdf_for_testing

app = FastAPI()

async def stream_rag_response(query: str):
    # User provided: initial state for astream includes documents as empty list
    async for output_chunk in rag_app.astream({"query": query, "documents": []}):
        if "generator" in output_chunk:
            # The generator node now yields a dict: {"token": "actual_token"}
            token_dict = output_chunk["generator"]
            if token_dict and "token" in token_dict:
                actual_token = token_dict["token"]
                # Ensure actual_token is not None before sending
                if actual_token is not None:
                     # User's SSE format: data: <content>


                     # Content here is the token itself.
                    yield f"data: {actual_token}\n\n"

@app.get("/rag_stream")
async def ask_question_stream(q: str = Query(..., min_length=1)):
    return StreamingResponse(stream_rag_response(q), media_type="text/event-stream")

async def index_documents_cli(pdf_directory: str):
    print(f"Starting indexing for PDF files in: {pdf_directory}")
    if not os.path.isdir(pdf_directory):
        print(f"Error: Directory not found: {pdf_directory}")
        if pdf_directory == "papermind/data/pdfs":
            print("Attempting to create and use a dummy PDF for indexing.")
            created_pdf_path = create_dummy_pdf_for_testing(pdf_dir=pdf_directory)
            if created_pdf_path and os.path.exists(created_pdf_path):
                if created_pdf_path.endswith(".pdf"):
                    await upsert_pdf_chunks(created_pdf_path)
                elif created_pdf_path.endswith(".txt"):
                    print(f"Skipping upsert for dummy .txt file: {created_pdf_path}. PyMuPDF is needed for PDF processing.")
            else:
                print("Failed to create or find a dummy PDF. Indexing cannot proceed.")
        return

    found_pdfs = False
    for filename in os.listdir(pdf_directory):
        if filename.lower().endswith(".pdf"):
            pdf_path = os.path.join(pdf_directory, filename)
            # print(f"Processing: {pdf_path}") # This line is in embed_index.upsert now
            try:
                await upsert_pdf_chunks(pdf_path) # upsert now prints its own status
                found_pdfs = True
            except Exception as e:
                print(f"Error processing {pdf_path}: {e}")

    if not found_pdfs and pdf_directory == "papermind/data/pdfs":
        print(f"No PDF files found in {pdf_directory}. Attempting to create and use a dummy PDF.")
        created_pdf_path = create_dummy_pdf_for_testing(pdf_dir=pdf_directory)
        if created_pdf_path and os.path.exists(created_pdf_path):
            if created_pdf_path.endswith(".pdf"):
                 await upsert_pdf_chunks(created_pdf_path)
            elif created_pdf_path.endswith(".txt"):
                 print(f"Skipping upsert for dummy .txt file: {created_pdf_path}. PyMuPDF is needed for PDF processing.")
        else:
            print("Failed to create or find a dummy PDF. Indexing cannot proceed.")


def main_cli():
    parser = argparse.ArgumentParser(description="PaperMind CLI")
    # User provided: required=True for subparsers
    subparsers = parser.add_subparsers(dest="command", help="Available commands", required=True)

    index_parser = subparsers.add_parser("index", help="Index PDF documents")
    index_parser.add_argument("--path", type=str, default="papermind/data/pdfs", help="Directory containing PDF files to index")

    serve_parser = subparsers.add_parser("serve", help="Run the FastAPI server")
    serve_parser.add_argument("--host", type=str, default="127.0.0.1", help="Host for the server")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port for the server")

    args = parser.parse_args()

    if args.command == "index":
        # User's logic for ensuring dummy PDF exists if path is default and empty
        if args.path == "papermind/data/pdfs":
            if not os.path.exists(args.path):
                print(f"Directory {args.path} not found. Creating it and a dummy PDF.")
                create_dummy_pdf_for_testing(pdf_dir=args.path)
            elif not any(f.lower().endswith(".pdf") for f in os.listdir(args.path)):
                 print(f"No PDFs found in {args.path}. Creating a dummy PDF.")
                 create_dummy_pdf_for_testing(pdf_dir=args.path)
        asyncio.run(index_documents_cli(args.path))
    elif args.command == "serve":
        print(f"Starting server on {args.host}:{args.port}")
        os.makedirs("papermind/store", exist_ok=True) # Ensure store dir exists
        dummy_pdf_default_dir = "papermind/data/pdfs"
        # User's logic to create dummy PDF before server start for DB check
        created_dummy_path = create_dummy_pdf_for_testing(pdf_dir=dummy_pdf_default_dir)

        try:
            # Use the renamed import for clarity
            client = ChromaServicePersistentClient(path="papermind/store")
            collection = client.get_or_create_collection("chunks")
            if collection.count() == 0:
                print("ChromaDB collection 'chunks' is empty.")
                if created_dummy_path and created_dummy_path.endswith(".pdf") and os.path.exists(created_dummy_path):
                    print(f"Attempting to index dummy PDF: {created_dummy_path}")
                    asyncio.run(upsert_pdf_chunks(created_dummy_path))
                elif created_dummy_path and created_dummy_path.endswith(".txt"):
                     print(f"Dummy file is a .txt ({created_dummy_path}), requires PyMuPDF for PDF processing to be indexed. Skipping auto-indexing.")
                else:
                    print("Dummy PDF could not be found or created as PDF, cannot auto-index for server start.")
            else:
                print(f"ChromaDB collection 'chunks' has {collection.count()} items.")
        except Exception as e:
            print(f"Error during pre-server DB check/indexing: {e}")
            print("This might happen if ChromaDB or PyMuPDF are not installed yet. Server will start but RAG might fail if no data is indexed.")
        uvicorn.run(app, host=args.host, port=args.port)
    else:
        parser.print_help()

if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("Warning: OPENAI_API_KEY not found in environment variables or .env file.")
        print("Please create a papermind/.env file with OPENAI_API_KEY='your_key'.")
    main_cli()
