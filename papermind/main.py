import asyncio
import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
import os
import argparse
import json

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

from papermind.agents.ask_graph import rag_app
from papermind.agents.embed_index import upsert as upsert_pdf_chunks
from chromadb import PersistentClient as ChromaServicePersistentClient
from papermind.tests.create_dummy import create_dummy_pdf_for_testing

app = FastAPI()

async def stream_rag_response(query: str):
    print(f"DEBUG: stream_rag_response: Starting for query: '{query}' using astream_events")
    initial_state = {"query": query, "documents": [], "current_token": ""}

    sse_event_count = 0
    last_yielded_token_for_sse = None

    # Using astream_events. version="v1" or "v2" might be needed depending on LangGraph version.
    # Let's assume "v1" for now or try without if it causes issues.
    # Most examples use version="v1" or "v2", "v1" is for older LangGraph.
    # Given the previous InvalidUpdateError, this langgraph version might be older.
    # Let's try version="v1" first. If not available, the tool will error and I can try "v2" or without.
    # Based on https://python.langchain.com/docs/langgraph/concepts/#streaming-events
    # it seems `version="v1"` is for specific LCEL event stream.
    # `astream_events` itself should provide node-level events.
    # The `streaming_events.py` example in LangGraph repo uses `astream_events(input, version="v1")` for `stream_chunk_to_event`
    # Let's use version="v1" as it's commonly seen with LLM streaming events.
    # If that doesn't work or gives wrong events, we might need version="v2" or a different approach.
    # For now, let's try with version="v1" as it's often related to streaming individual chunks.

    async for event in rag_app.astream_events(initial_state, version="v1"):
        event_name = event.get("event")
        event_data = event.get("data")
        event_node_name = event.get("name") # The name of the node the event is from

        print(f"DEBUG: stream_rag_response: RAW EVENT from astream_events: event_name='{event_name}', node='{event_node_name}', data='{event_data}'")

        actual_token_to_send = None

        # We are interested in tokens streamed from the 'generator' node.
        # LangGraph's 'on_chain_stream' or 'on_llm_stream' (if LLM is wrapped by LangChain)
        # or custom events might carry these.
        # If our 'generator' node directly yields dicts {'current_token': ...},
        # these might appear as data from an event related to the 'generator' node finishing a stream part.

        if event_name == "on_chain_stream" and event_node_name == "generator":
            # Check if 'chunk' in event_data contains our {'current_token': ...}
            # The structure of event_data['chunk'] can vary.
            # If the node itself (AsyncGenerator) yields {'current_token': X},
            # then event_data['chunk'] might be that dict.
            chunk_data = event_data.get("chunk")
            if isinstance(chunk_data, dict) and "current_token" in chunk_data:
                actual_token_to_send = chunk_data["current_token"]
                print(f"DEBUG: stream_rag_response (on_chain_stream): Extracted token: '{actual_token_to_send}' from chunk: {chunk_data}")

        # Alternative check: Sometimes the entire output of the node for that stream event is in 'data'
        # This depends on the LangGraph version and event type.
        # Let's also log if we see an 'on_chain_end' for the generator and what its data looks like.
        elif event_name == "on_chain_end" and event_node_name == "generator":
             print(f"DEBUG: stream_rag_response: Event 'on_chain_end' for 'generator'. Data: {event_data}")
             # This usually contains the final accumulated output of the node, not intermediate tokens.
             # However, good to log for understanding.

        if actual_token_to_send is not None:
            if actual_token_to_send != last_yielded_token_for_sse or actual_token_to_send == "": # Allow empty strings if distinct
                sse_event = f"data: {actual_token_to_send}\n\n"
                print(f"DEBUG: stream_rag_response: Yielding SSE Event #{sse_event_count + 1}: '{sse_event.strip()}' (Token: '{actual_token_to_send}')")
                yield sse_event
                last_yielded_token_for_sse = actual_token_to_send
                sse_event_count += 1
            else:
                print(f"DEBUG: stream_rag_response: Skipping yield for duplicate/same-as-last token: '{actual_token_to_send}'")
        # else:
            # This would be too verbose if not an error: print(f"DEBUG: stream_rag_response: No token extracted from this event.")

    print(f"DEBUG: stream_rag_response: Finished for query: '{query}'. Total SSE events yielded: {sse_event_count}")


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
            try:
                await upsert_pdf_chunks(pdf_path)
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
    subparsers = parser.add_subparsers(dest="command", help="Available commands", required=True)

    index_parser = subparsers.add_parser("index", help="Index PDF documents")
    index_parser.add_argument("--path", type=str, default="papermind/data/pdfs", help="Directory containing PDF files to index")

    serve_parser = subparsers.add_parser("serve", help="Run the FastAPI server")
    serve_parser.add_argument("--host", type=str, default="127.0.0.1", help="Host for the server")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port for the server")

    args = parser.parse_args()

    if args.command == "index":
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
        os.makedirs("papermind/store", exist_ok=True)
        dummy_pdf_default_dir = "papermind/data/pdfs"
        created_dummy_path = create_dummy_pdf_for_testing(pdf_dir=dummy_pdf_default_dir)

        try:
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
