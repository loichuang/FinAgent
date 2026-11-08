"""Encode every passage once with the dense model, in data/embeddings.npz."""
import time
from pathlib import Path

import numpy as np

from finagent.embed import EMBEDDINGS, MODEL_NAME, embed_passages
from finagent.search import load_passages

passages = load_passages()
start = time.time()
vectors = embed_passages([p["text"] for p in passages])
np.savez(EMBEDDINGS, ids=np.array([p["id"] for p in passages]), vectors=vectors)
print(f"{len(passages)} passages, {vectors.shape[1]} dimensions, {MODEL_NAME}, "
      f"{time.time() - start:.0f} s -> {EMBEDDINGS.name}")
