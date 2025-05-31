import json
import asyncio
import os
from typing import List, Dict, AsyncGenerator, TypedDict
from chromadb import Client
from langgraph.graph import StateGraph, END

from papermind.providers import chat, embedder

class GraphState(TypedDict):
    query: str
    documents: List[Dict]

async def retrieve_node(state: GraphState) -> Dict[str, List[Dict]]:
    query = state["query"]
    k_results = 10 # Number of documents to retrieve

    # Ensure papermind/store directory exists for ChromaDB client
    # This should ideally be handled at app startup or by the indexing process ensuring the dir exists.
    # Adding it here for robustness in case this node is called before indexing has created the dir.
    os.makedirs("papermind/store", exist_ok=True)

    coll = Client(path="papermind/store").get_or_create_collection("chunks")

    query_embedding = (await embedder.embed([query]))[0]

    results = coll.query(
        query_embeddings=[query_embedding],
        n_results=k_results,
        include=['documents', 'metadatas']
    )

    retrieved_docs = []
    if results.get("documents") and results.get("metadatas"):
        for doc_list, meta_list in zip(results["documents"], results["metadatas"]):
            for doc_str, meta in zip(doc_list, meta_list):
                try:
                    # Original document stored as JSON string in 'document' field by embed_index.py
                    # The 'document' from ChromaDB is the JSON string.
                    doc_content = json.loads(doc_str)
                    # We want to pass the full chunk data (header, body, page)
                    retrieved_docs.append(doc_content)
                except json.JSONDecodeError:
                    print(f"Error decoding document string: {doc_str}")
                    # Fallback or skip if necessary
                    retrieved_docs.append({"header": "Error", "body": "Could not parse document", "page": meta.get("page", "N/A") if meta else "N/A"})

    return {"documents": retrieved_docs}

async def generate_node(state: GraphState) -> AsyncGenerator[str, None]:
    query = state["query"]
    retrieved_chunks = state["documents"]

    final_messages = [{"role": "user", "content": query}]

    if retrieved_chunks:
        citations_header = "Use the following excerpts from the documents to answer the query. Cite page numbers for your sources (e.g., [p.PAGE_NUMBER]).\n\n"
        chunks_text = ""
        for chk in retrieved_chunks:
            page_num = chk.get('page', 'N/A')
            header = chk.get('header', 'N/A')
            body_preview = chk.get('body', '')[:500] # Limit body length for context
            chunks_text += f"[p.{page_num}] Header: {header}\nBody: {body_preview}...\n\n"
        final_messages.append({"role": "system", "content": citations_header + chunks_text.strip()})
    else:
        final_messages.append({"role": "system", "content": "No specific excerpts found. Answer based on general knowledge if possible, or state that the information isn't in the provided documents."})

    stream = await chat.stream(final_messages)
    async for chunk_item in stream:
        content_part = chunk_item.choices[0].delta.content
        if content_part is not None:
            yield content_part.lstrip()

workflow = StateGraph(GraphState)

workflow.add_node("retriever", retrieve_node)
workflow.add_node("generator", generate_node) # type: ignore

workflow.set_entry_point("retriever")
workflow.add_edge("retriever", "generator")
workflow.set_finish_point("generator")

rag_app = workflow.compile()
