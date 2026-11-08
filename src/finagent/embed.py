"""Dense embeddings of the passages and of the questions, with a local BGE model.

The passages are encoded once (scripts/embed.py) and saved in data/embeddings.npz; a
question is encoded when it is asked. Every vector is normalised to length 1, so the
cosine of two vectors is their dot product.
"""

from functools import lru_cache
from pathlib import Path

import numpy as np

MODEL_NAME = "BAAI/bge-small-en-v1.5"  # 33 M parameters, 384 dimensions, 512 tokens at most
# BGE was trained with this instruction in front of the queries, never of the passages
QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "
EMBEDDINGS = Path(__file__).resolve().parents[2] / "data" / "embeddings.npz"


@lru_cache(maxsize=1)
def model():
    """The embedding model, loaded once (downloaded from Hugging Face the first time)."""
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL_NAME)


def embed_passages(texts: list[str], batch_size: int = 32) -> np.ndarray:
    """One normalised vector per passage, as rows of an (n, 384) matrix."""
    return model().encode(texts, batch_size=batch_size, normalize_embeddings=True,
                          show_progress_bar=True, convert_to_numpy=True)


def embed_query(question: str) -> np.ndarray:
    """The normalised vector of a question, instruction included, of shape (384,)."""
    return model().encode(QUERY_INSTRUCTION + question, normalize_embeddings=True,
                          convert_to_numpy=True)


def load_embeddings(path: Path = EMBEDDINGS) -> dict[str, np.ndarray]:
    """Passage id -> its normalised vector, as saved by scripts/embed.py."""
    data = np.load(path)
    return dict(zip(data["ids"].tolist(), data["vectors"]))
