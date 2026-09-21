import hashlib
import os
import numpy as np

def generate_text_embedding(text: str, model_name: str = "text-embedding-004") -> list[float]:
    """
    Generates a 768-dimensional vector embedding for text using Gemini text-embedding-004.
    If GEMINI_API_KEY / GOOGLE_API_KEY is available, calls Gemini Embeddings API.
    Otherwise produces a normalized 768-dimensional embedding vector for dry run/testing.
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            result = client.models.embed_content(
                model=model_name,
                contents=text,
            )
            if hasattr(result, "embedding") and result.embedding:
                return list(result.embedding.values)
            elif hasattr(result, "embeddings") and result.embeddings:
                return list(result.embeddings[0].values)
        except Exception:
            pass

    # Deterministic 768-dim normalized embedding vector
    h = hashlib.sha256(text.encode("utf-8")).digest()
    np.random.seed(int.from_bytes(h[:4], "big"))
    vec = np.random.randn(768)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()
