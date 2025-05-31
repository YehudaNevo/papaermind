import json
import asyncio
from typing import List, Dict, AsyncGenerator, TypedDict, Annotated
from chromadb import Client
from langgraph.graph import StateGraph, END
import langgraph.prebuilt as lg_prebuilt # For add_messages_node if needed, not for this simple case

# Corrected imports from other project modules
from papermind.providers import chat, embedder

# Define the state for the graph
class GraphState(TypedDict):
    query: str
    # The final answer will be streamed, so we don't store it in the state directly here.
    # Instead, the node will be an async generator.

async def retrieve_chunks_async(query: str, k: int = 8) -> List[Dict]:
    # Ensure the 'store' directory might exist if not created by upsert yet
    # However, typically collection is assumed to exist.
    # For robustness: os.makedirs("papermind/store", exist_ok=True)
    coll = Client(path="papermind/store").get_or_create_collection("chunks") # get_or_create for safety

    query_embedding = (await embedder.embed([query]))[0]

    results = coll.query(
        query_embeddings=[query_embedding],
        n_results=k
    )

    documents = results.get("documents")
    if documents and len(documents) > 0:
        return [json.loads(doc) for doc in documents[0]]
    return []

# This will be our single node in the graph. It's an async generator.
async def answer_generation_node(state: GraphState) -> AsyncGenerator[str, None]:
    query = state["query"]

    retrieved_chunks = await retrieve_chunks_async(query)

    context_messages = [
        {"role": "user", "content": f"Answer the following query based on the provided context. Query: {query}"}
    ]

    if not retrieved_chunks:
        context_messages.append({
            "role": "system",
            "content": "No relevant context found. Please answer based on your general knowledge or indicate that the information is not available in the provided documents."
        })
    else:
        context_str = "\n\n---\n\n".join(
            f"[Page {chunk.get('page', 'N/A')}] {chunk.get('header', 'No Header')}\n{chunk.get('body', '')[:1000]}"
            for chunk in retrieved_chunks
        )
        context_messages.append({
            "role": "system",
            "content": f"Context from documents:\n{context_str}"
        })

    # The original snippet's prompt structure:
    # ctx = [{"role":"user","content":
    #         f"Answer from the following excerpts (cite page numbers):
{q}"}]
    # for chk in retrieve(q):
    #     ctx.append({"role":"system",
    #                 "content":f"[p.{chk['page']}] {chk['body'][:1000]}"})
    # This is also a good way. Let's refine to match that more closely for citation.

    final_messages = [{"role": "user", "content": query}]
    if retrieved_chunks:
        citations_header = "Use the following excerpts from the documents to answer the query. Cite page numbers for your sources (e.g., [p.PAGE_NUMBER]).\n\n"
        chunks_text = ""
        for chk in retrieved_chunks:
            chunks_text += f"[p.{chk.get('page', 'N/A')}] Header: {chk.get('header', 'N/A')}\nBody: {chk.get('body', '')[:500]}...\n\n" # Limit body for context window
        final_messages.append({"role": "system", "content": citations_header + chunks_text.strip()})
    else:
        final_messages.append({"role": "system", "content": "No specific excerpts found. Answer based on general knowledge if possible, or state that the information isn't in the provided documents."})

    stream = await chat.stream(final_messages)
    async for chunk_item in stream:
        content_part = chunk_item.choices[0].delta.content
        if content_part is not None:
            yield content_part

# Workflow setup
workflow = StateGraph(GraphState)

# Add the single node that performs retrieval and generation
# The node's output (the stream) is implicitly handled by LangGraph's astream/invoke methods
# when the node is an async generator.
workflow.add_node("generate_answer", answer_generation_node) # type: ignore

# Set the entry and finish points
workflow.set_entry_point("generate_answer")
workflow.set_finish_point("generate_answer") # For a single node graph

# Compile the graph
# The `checkpointer` is optional, good for production but not strictly needed for MVP
# from langgraph.checkpoints.sqlite import SqliteSaver
# memory = SqliteSaver.from_conn_string(":memory:")
# rag_app = workflow.compile(checkpointer=memory)
rag_app = workflow.compile()

# To run this (example, will be in main.py or FastAPI):
# async def main_test():
#     query = "What is the main topic of the document?"
#     # The input to the graph is the state object or a dict that matches the state.
#     # For astream, the input is usually the initial state values.
#     async for output_chunk in rag_app.astream({"query": query}):
#         # output_chunk will be the yielded string parts from answer_generation_node
#         # In a streaming scenario, these are dicts like {"generate_answer": "token"}
#         if "generate_answer" in output_chunk:
#             print(output_chunk["generate_answer"], end="")
#
# if __name__ == "__main__":
# asyncio.run(main_test())
