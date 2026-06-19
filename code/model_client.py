from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from io_data import ImagePayload


DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class ModelClientError(RuntimeError):
    pass


class ModelClient(Protocol):
    def generate_json(self, system_prompt: str, user_prompt: str, images: list[ImagePayload]) -> str:
        ...


@dataclass
class GeminiModelClient:
    api_key: str | None = None
    model: str | None = None
    timeout_seconds: int = 60

    def __post_init__(self) -> None:
        self.api_key = self.api_key or os.getenv("GEMINI_API_KEY")
        self.model = self.model or os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
        if not self.api_key:
            raise ModelClientError("GEMINI_API_KEY is required")

    def generate_json(self, system_prompt: str, user_prompt: str, images: list[ImagePayload]) -> str:
        url = GEMINI_ENDPOINT.format(model=self.model) + f"?key={self.api_key}"
        parts: list[dict[str, object]] = [{"text": user_prompt}]
        parts.extend(
            {
                "inlineData": {
                    "mimeType": image.media_type,
                    "data": image.base64_data,
                }
            }
            for image in images
        )
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.0,
            },
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise ModelClientError(f"Gemini HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ModelClientError(f"Gemini request failed: {type(exc).__name__}: {exc}") from exc

        try:
            return body["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelClientError("Gemini response did not contain JSON text") from exc
