"""LLM access behind one small interface, so the rest of the app never knows which vendor is used."""

import hashlib
import json
import math
import re
from functools import lru_cache
from typing import Protocol

import httpx

from app.config import Settings, get_settings


class LLMError(RuntimeError):
    pass


class LLMProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    def chat(self, system: str, user: str, json_mode: bool = False) -> str: ...


class OpenAICompatibleProvider:
    """Works with any OpenAI-compatible endpoint: Ollama (/v1), OpenAI, vLLM, LM Studio, ..."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = httpx.Client(
            base_url=settings.llm_base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            timeout=120,
        )

    def _post(self, path: str, body: dict) -> dict:
        try:
            response = self.client.post(path, json=body)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM request to {path} failed: {exc}") from exc

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for i in range(0, len(texts), 64):  # batch to keep requests small
            data = self._post("/embeddings", {"model": self.settings.embedding_model, "input": texts[i : i + 64]})
            vectors.extend(item["embedding"] for item in sorted(data["data"], key=lambda d: d["index"]))
        if vectors and len(vectors[0]) != self.settings.embedding_dim:
            raise LLMError(
                f"Embedding model returned {len(vectors[0])} dimensions, "
                f"but EMBEDDING_DIM is {self.settings.embedding_dim}"
            )
        return vectors

    def chat(self, system: str, user: str, json_mode: bool = False) -> str:
        body: dict = {
            "model": self.settings.chat_model,
            "temperature": 0,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        data = self._post("/chat/completions", body)
        return data["choices"][0]["message"]["content"]


class FakeProvider:
    """Offline provider: hashed bag-of-words embeddings and an extractive "chat".

    Good enough for real keyword-level retrieval in tests and for a demo without any model.
    """

    def __init__(self, dim: int):
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in re.findall(r"\w+", text.lower()):
            h = int(hashlib.md5(token.encode()).hexdigest(), 16)
            vec[h % self.dim] += 1.0 if (h >> 64) % 2 else -1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def chat(self, system: str, user: str, json_mode: bool = False) -> str:
        if json_mode:
            return json.dumps({})
        match = re.search(r"\[1\][^\n]*\n(.+?)(?:\n\n\[2\]|\n\nQuestion:|\Z)", user, re.S)
        snippet = match.group(1).strip()[:300] if match else "No context."
        return f"(offline demo answer) {snippet} [1]"


@lru_cache
def get_llm() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "fake":
        return FakeProvider(settings.embedding_dim)
    if settings.llm_provider == "openai":
        return OpenAICompatibleProvider(settings)
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider}")
