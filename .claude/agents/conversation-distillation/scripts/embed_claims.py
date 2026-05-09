"""
Compute embeddings for atomic claims.

Embeddings live in `state/embeddings.npz`, keyed by claim ID. The default
model is BAAI/bge-base-en-v1.5 — a 768-dim open model that runs offline,
including on Apple Silicon via the standard sentence-transformers stack.

Override with `state/protocol_config.json` (key: embedding_model).

`--since-mark` only embeds claims added since the last run, using a
position marker file. Re-runs are cheap.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from state_io import (  # noqa: E402
    iter_claims, load_config, log_event, save_config, state_dir,
)


EMB_PATH = lambda: state_dir() / "embeddings.npz"  # noqa: E731
MARK_PATH = lambda: state_dir() / "embedding_mark.json"  # noqa: E731


def load_embeddings() -> tuple[list[str], np.ndarray]:
    """Return (claim_ids, matrix) where matrix[i] is the embedding for claim_ids[i]."""
    p = EMB_PATH()
    if not p.exists():
        return [], np.zeros((0, 0), dtype=np.float32)
    data = np.load(p, allow_pickle=False)
    return list(data["ids"]), data["vectors"]


def save_embeddings(ids: list[str], vectors: np.ndarray) -> None:
    p = EMB_PATH()
    p.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(p, ids=np.array(ids), vectors=vectors)


def load_mark() -> dict:
    p = MARK_PATH()
    if not p.exists():
        return {"last_embedded_count": 0}
    with open(p, "r") as f:
        return json.load(f)


def save_mark(mark: dict) -> None:
    p = MARK_PATH()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as f:
        json.dump(mark, f, indent=2)


# ---------------------------------------------------------------------------
# Embedding model lazy-load
# ---------------------------------------------------------------------------


_MODEL_CACHE: dict = {}


def get_model(name: str):
    if name in _MODEL_CACHE:
        return _MODEL_CACHE[name]
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        raise RuntimeError(
            "sentence-transformers is required for embedding. "
            "Install with: pip install sentence-transformers"
        ) from e
    model = SentenceTransformer(name)
    _MODEL_CACHE[name] = model
    return model


def embed_texts(texts: list[str], model_name: str) -> np.ndarray:
    """Return an L2-normalized matrix of shape (len(texts), embedding_dim)."""
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    model = get_model(model_name)
    vectors = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    return np.asarray(vectors, dtype=np.float32)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    p = argparse.ArgumentParser(description="Compute embeddings for atomic claims.")
    p.add_argument("--since-mark", action="store_true",
                   help="Only embed claims added since last run")
    p.add_argument("--all", action="store_true",
                   help="Re-embed every claim in the library (use after embedding-model change)")
    p.add_argument("--model", default=None,
                   help="Override the embedding model from protocol_config.json")
    args = p.parse_args()

    cfg = load_config()
    model_name = args.model or cfg["embedding_model"]
    if cfg["embedding_model"] != model_name:
        cfg["embedding_model"] = model_name
        save_config(cfg)
        log_event("embedding_model_changed", new_model=model_name)
        # Force re-embed everything after a model change
        args.all = True

    existing_ids, existing_vecs = load_embeddings()
    existing_set = set(existing_ids)

    mark = load_mark()
    skip_count = 0 if args.all else mark.get("last_embedded_count", 0)

    # Stream claims, collect only those that need embedding
    to_embed: list[tuple[str, str]] = []
    seen = 0
    for c in iter_claims():
        seen += 1
        if seen <= skip_count:
            continue
        cid = c["id"]
        if not args.all and cid in existing_set:
            continue
        prop = c.get("proposition", "").strip()
        if not prop:
            continue
        to_embed.append((cid, prop))

    if not to_embed:
        print(f"Nothing to embed. {len(existing_ids)} claims already embedded.")
        return 0

    print(f"Embedding {len(to_embed)} claim(s) with {model_name}...")
    new_ids = [t[0] for t in to_embed]
    new_texts = [t[1] for t in to_embed]
    new_vecs = embed_texts(new_texts, model_name)

    if args.all:
        # Replace everything
        all_ids = new_ids
        all_vecs = new_vecs
    else:
        if existing_vecs.size == 0:
            all_ids = new_ids
            all_vecs = new_vecs
        else:
            all_ids = existing_ids + new_ids
            all_vecs = np.vstack([existing_vecs, new_vecs])

    save_embeddings(all_ids, all_vecs)
    save_mark({"last_embedded_count": seen, "model": model_name})

    log_event(
        "claims_embedded",
        embedded_now=len(to_embed),
        total_in_index=len(all_ids),
        model=model_name,
    )
    print(f"Embedded {len(to_embed)} new claims; index now contains {len(all_ids)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
