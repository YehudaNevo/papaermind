import json, os
from typing import List, Dict, TypedDict, AsyncGenerator
from chromadb import PersistentClient
from langgraph.graph import StateGraph
from papermind.providers import chat, embedder

class GraphState(TypedDict):
    query: str
    documents: List[Dict]

async def retrieve_node(state: GraphState) -> Dict[str, List[Dict]]:
    query = state["query"]
    coll = PersistentClient(path="papermind/store").get_or_create_collection("chunks")
    vec = (await embedder.embed([query]))[0]
    res = coll.query(query_embeddings=[vec], n_results=10, include=["documents"])
    docs = []
    for s in res.get("documents", [])[0]:
        try:
            docs.append(json.loads(s))
        except:
            pass
    return {"documents": docs}

async def generate_node(state: GraphState) -> AsyncGenerator[Dict[str, str], None]:
    query = state["query"]
    chunks = state["documents"]
    msgs = [{"role": "user", "content": query}]
    if chunks:
        ctx = "\n".join(f"[p.{c.get('page')}] {c.get('body')[:500]}" for c in chunks)
        msgs.append({"role": "system", "content": ctx})

    print(f"DEBUG: generate_node: Sending messages to LLM: {json.dumps(msgs, indent=2)}") # LOGGING
    stream = await chat.stream(msgs)
    async for part in stream:
        tok = part.choices[0].delta.content
        print(f"DEBUG: generate_node: Raw LLM Token: '{tok}'") # LOGGING
        if tok:
            processed_token = tok.lstrip()
            print(f"DEBUG: generate_node: Yielding: {{'token': '{processed_token}'}}") # LOGGING
            yield {"token": processed_token}
        elif tok is None:
            print("DEBUG: generate_node: Received None token from LLM stream.") # LOGGING
        else: # tok is an empty string ""
            print("DEBUG: generate_node: Received empty string token from LLM stream.") # LOGGING


wf = StateGraph(GraphState)
wf.add_node("retriever", retrieve_node)
wf.add_node("generator", generate_node)
wf.set_entry_point("retriever")
wf.add_edge("retriever", "generator")
wf.set_finish_point("generator")
rag_app = wf.compile()
