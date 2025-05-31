import asyncio
import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
import os
import argparse # For CLI arguments

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))


# Import from other project modules
# These imports assume 'papermind' is in PYTHONPATH or you run with 'python -m papermind.main'
# For simplicity, if running 'python papermind/main.py' directly from project root,
# ensure papermind is discoverable (e.g. by adding project root to PYTHONPATH or using a proper package structure)
# Assuming we run from the root of the project as 'python papermind/main.py'
# We might need to adjust sys.path if papermind package is not installed.
# A common way is to have an __init__.py in papermind and run as module.
# For now, let's assume the execution environment handles Python path correctly.
from papermind.agents.ask_graph import rag_app # The compiled LangGraph app
from papermind.agents.embed_index import upsert as upsert_pdf_chunks # Renamed for clarity
# from papermind.data.pdfs import dummy_pdf_content # We'll create this for testing indexing - replaced with local function

# Create a dummy PDF for testing if it doesn't exist
def create_dummy_pdf_for_testing(pdf_dir="papermind/data/pdfs", pdf_name="dummy.pdf"):
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_path = os.path.join(pdf_dir, pdf_name)
    if not os.path.exists(pdf_path):
        try:
            from fitz import Document
            doc = Document()
            page = doc.new_page()
            page.insert_text((72, 72), "Test PDF Content", fontsize=12)
            page.insert_text((72, 100), "CHAPTER 1: Introduction", fontsize=16)
            page.insert_text((72, 120), "This is the first paragraph of the introduction.", fontsize=11)
            page.insert_text((72, 150), "Section 1.1: Background", fontsize=14)
            page.insert_text((72, 170), "Some background information here.", fontsize=11)
            doc.save(pdf_path)
            print(f"Created dummy PDF: {pdf_path}")
            return pdf_path
        except Exception as e:
            print(f"Could not create dummy PDF (PyMuPDF/fitz probably not installed yet): {e}")
            # Create an empty text file instead if fitz fails (e.g. in a bare env)
            fallback_path = os.path.join(pdf_dir, "dummy.txt") # Ensure it's in the correct dir
            with open(fallback_path, "w") as f:
                f.write("CHAPTER 1: Introduction\nThis is a test.")
            print(f"Created dummy text file as fallback: {fallback_path}")
            return fallback_path # Return .txt path so chunker can try
    return pdf_path

app = FastAPI()

# This generator will adapt LangGraph's astream output for FastAPI's StreamingResponse
async def stream_rag_response(query: str):
    # Input to the graph is a dictionary matching the GraphState
    async for output_chunk in rag_app.astream({"query": query}):
        # Assuming the relevant output is from the "generate_answer" node
        if "generate_answer" in output_chunk:
            token = output_chunk["generate_answer"]
            if token: # Ensure token is not empty or None
                yield token # Removed extra newlines, event-stream handles separation

@app.get("/rag_stream") # Changed from /rag to /rag_stream to avoid conflict with Next.js /rag page route
async def ask_question_stream(q: str = Query(..., min_length=1)):
    return StreamingResponse(stream_rag_response(q), media_type="text/event-stream")

# CLI for indexing
async def index_documents_cli(pdf_directory: str):
    print(f"Starting indexing for PDF files in: {pdf_directory}")
    if not os.path.isdir(pdf_directory):
        print(f"Error: Directory not found: {pdf_directory}")
        # Create a dummy PDF for testing if the specified dir is the default one and doesn't exist
        if pdf_directory == "papermind/data/pdfs":
            print("Attempting to create and use a dummy PDF for indexing.")
            created_pdf_path = create_dummy_pdf_for_testing(pdf_dir=pdf_directory) # Pass correct dir
            if created_pdf_path and os.path.exists(created_pdf_path):
                if created_pdf_path.endswith(".pdf"):
                    await upsert_pdf_chunks(created_pdf_path)
                elif created_pdf_path.endswith(".txt"):
                    print(f"Skipping upsert for dummy .txt file: {created_pdf_path}. PyMuPDF is needed for PDF processing.")
            else:
                print("Failed to create or find a dummy PDF. Indexing cannot proceed.")
            return
        else: # If it's not the default dir and doesn't exist, just return.
            return


    found_pdfs = False
    for filename in os.listdir(pdf_directory):
        if filename.lower().endswith(".pdf"):
            pdf_path = os.path.join(pdf_directory, filename)
            print(f"Processing: {pdf_path}")
            try:
                await upsert_pdf_chunks(pdf_path) # Call the async upsert function
                found_pdfs = True
            except Exception as e:
                print(f"Error processing {pdf_path}: {e}")

    if not found_pdfs and pdf_directory == "papermind/data/pdfs":
        print(f"No PDF files found in {pdf_directory}. Attempting to create and use a dummy PDF.")
        created_pdf_path = create_dummy_pdf_for_testing(pdf_dir=pdf_directory) # Call again to ensure it exists
        if created_pdf_path and os.path.exists(created_pdf_path):
            if created_pdf_path.endswith(".pdf"):
                 await upsert_pdf_chunks(created_pdf_path)
            elif created_pdf_path.endswith(".txt"):
                 print(f"Skipping upsert for dummy .txt file: {created_pdf_path}. PyMuPDF is needed for PDF processing.")
        else:
            print("Failed to create or find a dummy PDF. Indexing cannot proceed.")


def main_cli():
    parser = argparse.ArgumentParser(description="PaperMind CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands", required=True)

    # Subparser for the 'index' command
    index_parser = subparsers.add_parser("index", help="Index PDF documents")
    index_parser.add_argument(
        "--path",
        type=str,
        default="papermind/data/pdfs",
        help="Directory containing PDF files to index"
    )

    # Subparser for the 'serve' command
    serve_parser = subparsers.add_parser("serve", help="Run the FastAPI server")
    serve_parser.add_argument("--host", type=str, default="127.0.0.1", help="Host for the server")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port for the server")

    args = parser.parse_args()

    if args.command == "index":
        # Create dummy PDF before indexing if the default path is used and it's empty or doesn't exist
        if args.path == "papermind/data/pdfs":
            # Check if dir exists, if not create it along with dummy
            if not os.path.exists(args.path):
                print(f"Directory {args.path} not found. Creating it and a dummy PDF.")
                create_dummy_pdf_for_testing(pdf_dir=args.path) # This will create the dir
            # If dir exists but no PDFs, create dummy
            elif not any(f.lower().endswith(".pdf") for f in os.listdir(args.path)):
                 print(f"No PDFs found in {args.path}. Creating a dummy PDF.")
                 create_dummy_pdf_for_testing(pdf_dir=args.path)

        asyncio.run(index_documents_cli(args.path))
    elif args.command == "serve":
        print(f"Starting server on {args.host}:{args.port}")

        # Ensure papermind/store directory exists for ChromaDB
        os.makedirs("papermind/store", exist_ok=True)

        # Ensure dummy PDF exists for potential first query if no indexing was done
        # and index it if the DB is empty.
        dummy_pdf_default_dir = "papermind/data/pdfs"
        created_dummy_path = create_dummy_pdf_for_testing(pdf_dir=dummy_pdf_default_dir)

        try:
            from chromadb import Client # Local import for this specific check
            client = Client(path="papermind/store")
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
    # This allows running 'python papermind/main.py <command>'
    # For uvicorn live reload, use 'uvicorn papermind.main:app --reload --reload-dir papermind'
    # Ensure OPENAI_API_KEY is set in .env or environment
    if not os.getenv("OPENAI_API_KEY"):
        print("Warning: OPENAI_API_KEY not found in environment variables or .env file.")
        print("Please create a papermind/.env file with OPENAI_API_KEY='your_key'.")

    main_cli()
