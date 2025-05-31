import os
from typing import Protocol, List
from openai import AsyncOpenAI

class Embedder(Protocol):
    async def embed(self, texts: List[str]) -> List[List[float]]: ...

class Chat(Protocol):
    async def stream(self, messages): ...

class OpenAIEmbedder:
    def __init__(self, model="text-embedding-3-small"):
        self.cli = AsyncOpenAI()
        self.model = model

    async def embed(self, texts):
        resp = await self.cli.embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in resp.data]

class OpenAIChat:
    def __init__(self, model="gpt-4o"):
        self.cli = AsyncOpenAI()
        self.model = model

    async def stream(self, messages):
        return await self.cli.chat.completions.create(
            model=self.model, messages=messages, stream=True
        )

embedder: Embedder = OpenAIEmbedder()
chat: Chat       = OpenAIChat()
