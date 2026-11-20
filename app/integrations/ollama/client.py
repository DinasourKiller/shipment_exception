"""Ollama Local AI REST Client.

Provides async client connectivity to local Ollama inference server (defaulting to gemma2:2b),
with structured JSON generation and error isolation.
"""

from typing import Any, Dict, Optional
import httpx

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger("control_tower.integrations.ollama")
settings = get_settings()


class OllamaClient:
    """Async client communicating with local Ollama runtime."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL
        self.timeout = timeout_seconds or float(settings.OLLAMA_TIMEOUT_SECONDS)
        self.transport = transport

    async def check_health(self) -> Dict[str, Any]:
        """Verify connectivity to local Ollama server and check model availability."""
        url = f"{self.base_url}/api/tags"
        try:
            async with httpx.AsyncClient(timeout=3.0, transport=self.transport) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    models = [m.get("name") for m in res.json().get("models", [])]
                    has_model = any(self.model in m for m in models)
                    return {
                        "status": "online",
                        "model_configured": self.model,
                        "model_available": has_model,
                        "installed_models": models,
                    }
                return {"status": "degraded", "http_status": res.status_code}
        except Exception as err:
            logger.debug("Ollama healthcheck failed: %s", err)
            return {
                "status": "offline",
                "model_configured": self.model,
                "reason": str(err),
            }

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        format_json: bool = True,
    ) -> Optional[str]:
        """Invokes Ollama /api/generate endpoint returning text or structured JSON string."""
        url = f"{self.base_url}/api/generate"
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if format_json:
            payload["format"] = "json"

        try:
            logger.info("Dispatching prompt to Ollama model '%s'", self.model)
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    response_text = data.get("response", "").strip()
                    logger.debug("Ollama generation completed in %s ns", data.get("total_duration"))
                    return response_text
                else:
                    logger.warning("Ollama returned non-200 status: %s - %s", res.status_code, res.text)
                    return None
        except httpx.ConnectError:
            logger.info("Local Ollama server is not running at %s. Engaging deterministic fallback.", self.base_url)
            return None
        except httpx.TimeoutException:
            logger.warning("Ollama inference timed out after %s seconds. Engaging fallback.", self.timeout)
            return None
        except Exception as err:
            logger.warning("Unexpected error during Ollama generation: %s", err)
            return None
