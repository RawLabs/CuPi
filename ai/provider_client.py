import json
import requests
from PySide6.QtCore import QThread, Signal
from typing import List, Dict, Any, Optional


def is_vision_model(item: dict) -> bool:
    modality = str(item.get("architecture", {}).get("modality", "")).lower()
    m_id = str(item.get("id", "")).lower()

    if "image" in modality or "vision" in modality or "multimodal" in modality:
        return True

    vision_keywords = [
        "vision", "-vl", "llava", "pixtral", "minicpm", "moondream", "cogvlm",
        "gemini", "claude-3", "gpt-4o", "gpt-4-turbo", "gpt-5", "qwen2-vl",
        "qwen3", "gemma-4", "multimodal", "fuyu", "internlm-xcomposer"
    ]
    return any(kw in m_id for kw in vision_keywords)


def is_free_model(item: dict) -> bool:
    m_id = str(item.get("id", "")).lower()
    if ":free" in m_id or "-free" in m_id:
        return True
    pricing = item.get("pricing", {})
    if pricing and pricing.get("prompt") == "0" and pricing.get("completion") == "0":
        return True
    return False


def describe_missing_completion(result: Any, provider: str, model: str) -> str:
    """Explain a successful-looking provider response that contains no completion."""
    if not isinstance(result, dict):
        preview = json.dumps(result, default=str)[:500]
        return f"{provider} returned an invalid completion response for '{model}': {preview}"

    error = result.get("error")
    if isinstance(error, dict):
        detail = str(error.get("message") or error.get("code") or "unknown provider error")
    elif error:
        detail = str(error)
    else:
        detail = "no choices were included"

    preview = json.dumps(result, default=str)[:500]
    return (
        f"{provider} returned no completion for '{model}' ({detail}). "
        f"Response preview: {preview}"
    )


class ModelFetchWorker(QThread):
    models_fetched = Signal(list, str)  # (model_metadata_list, error_message)

    def __init__(self, provider: str, base_url: str, api_key: str = ""):
        super().__init__()
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def run(self):
        try:
            url = f"{self.base_url}/models"
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            if self.provider == "openrouter":
                headers["X-Title"] = "cupi"

            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                models = []
                if "data" in data and isinstance(data["data"], list):
                    for item in data["data"]:
                        model_id = item.get("id")
                        if model_id:
                            models.append({
                                "id": model_id,
                                "is_vision": is_vision_model(item),
                                "is_free": is_free_model(item)
                            })
                self.models_fetched.emit(models, "")
            else:
                self.models_fetched.emit([], f"Server returned status {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            self.models_fetched.emit([], f"Connection failed: {str(e)}")


class InferenceWorker(QThread):
    response_ready = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, provider: str, base_url: str, api_key: str, model: str, messages: List[Dict[str, Any]]):
        super().__init__()
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or "lm-studio"
        self.model = model
        self.messages = messages

    def run(self):
        try:
            url = f"{self.base_url}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            if self.provider == "openrouter":
                headers["X-Title"] = "cupi"

            payload = {
                "model": self.model,
                "messages": self.messages,
                "max_tokens": 4096,
                "temperature": 0.3
            }

            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            if resp.status_code == 200:
                result = resp.json()
                choices = result.get("choices", [])
                if choices and isinstance(choices, list) and len(choices) > 0:
                    first_choice = choices[0]
                    msg_obj = first_choice.get("message", {}) if isinstance(first_choice, dict) else {}
                    content = msg_obj.get("content") or msg_obj.get("reasoning") or msg_obj.get("reasoning_content") or first_choice.get("text") or ""

                    if not content and "error" in result:
                        err_msg = result["error"].get("message", "Model provider returned an error structure.")
                        self.error_occurred.emit(f"Provider Error: {err_msg}")
                    elif content:
                        text = str(content)
                        if first_choice.get("finish_reason") == "length":
                            text += "\n\n> This response reached the model output limit and may be incomplete. Ask for the remaining sections before exporting."
                        self.response_ready.emit(text)
                    else:
                        raw_preview = json.dumps(result)[:150]
                        self.error_occurred.emit(f"Model returned empty content structure. Raw response: {raw_preview}")
                else:
                    self.error_occurred.emit(
                        describe_missing_completion(result, self.provider, self.model)
                    )
            else:
                err_text = resp.text
                try:
                    err_json = resp.json()
                    if isinstance(err_json, dict) and "error" in err_json:
                        msg = str(err_json["error"].get("message", ""))
                        raw_detail = str(err_json["error"].get("metadata", {}).get("raw", ""))
                        if "DEGRADED" in raw_detail or "DEGRADED" in msg or "DEGRADED" in err_text:
                            self.error_occurred.emit(
                                f"OpenRouter Model Degraded (400): The selected model route ('{self.model}') is currently experiencing provider backend degradation. Please select another vision model (e.g. 'meta-llama/llama-3.3-70b-instruct:free', 'google/gemini-2.0-flash-001', or 'openai/gpt-4o-mini') or switch to LM Studio (Local)."
                            )
                            return
                except Exception:
                    pass

                self.error_occurred.emit(f"API Error ({resp.status_code}): {err_text[:200]}")
        except requests.exceptions.Timeout:
            self.error_occurred.emit("Request timed out. Please verify your model server is responding.")
        except requests.exceptions.ConnectionError:
            self.error_occurred.emit(f"Cannot connect to {self.base_url}. Ensure server is running.")
        except Exception as e:
            self.error_occurred.emit(f"Inference error: {str(e)}")
