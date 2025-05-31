import json, os
from typing import List, Dict, TypedDict, AsyncGenerator
from chromadb import PersistentClient # User updated this
from langgraph.graph import StateGraph
from papermind.providers import chat, embedder

class GraphState(TypedDict):
    query: str
    documents: List[Dict]

async def retrieve_node(state: GraphState) -> Dict[str, List[Dict]]:
    query = state["query"]
    # User updated to PersistentClient
    coll = PersistentClient(path="papermind/store").get_or_create_collection("chunks")
    vec = (await embedder.embed([query]))[0]
    # User updated include to just "documents"
    res = coll.query(query_embeddings=[vec], n_results=10, include=["documents"])
    docs = []
    # User added try-except for robustness
    for s in res.get("documents", [])[0]:
        try:
            docs.append(json.loads(s))
        except: # Catch all exceptions during json.loads
            pass # Skip if a document string is not valid JSON
    return {"documents": docs}

async def generate_node(state: GraphState) -> AsyncGenerator[Dict[str, str], None]: # Yields dict now
    query = state["query"]
    chunks = state["documents"]
    msgs = [{"role": "user", "content": query}]
    if chunks:
        # User updated context string formatting
        ctx = "\n".join(f"[p.{c.get('page')}] {c.get('body')[:500]}" for c in chunks)
        msgs.append({"role": "system", "content": ctx})
    stream = await chat.stream(msgs)
    async for part in stream:
        tok = part.choices[0].delta.content
        if tok:
            yield {"token": tok.lstrip()} # Yields a dict {"token": ...}

wf = StateGraph(GraphState)
wf.add_node("retriever", retrieve_node)
wf.add_node("generator", generate_node)
wf.set_entry_point("retriever")
wf.add_edge("retriever", "generator")
wf.set_finish_point("generator")
rag_app = wf.compile()
