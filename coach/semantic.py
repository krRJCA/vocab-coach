"""AI meaning check: accept answers that use different words but mean the same.

A pretrained Korean sentence-embedding model from Hugging Face
(jhgan/ko-sroberta-multitask) turns sentences into vectors; similar
meanings give a high cosine similarity.

Embeddings are good at overall meaning but weak at small details
(만 원 vs 이만 원, 아이스 vs 따뜻한), so an answer must also pass the
fact rules in checker.py. Run evaluate.py to see how well this works.
"""

from functools import lru_cache

from coach.checker import fact_problem

MODEL_NAME = "jhgan/ko-sroberta-multitask"
THRESHOLD = 0.80


@lru_cache(maxsize=1)
def load_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME)


def is_available():
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        return False
    return True


def similarity(answer, accepted):
    """Highest cosine similarity between the answer and any accepted form."""
    from sentence_transformers import util

    model = load_model()
    embeddings = model.encode([answer, *accepted], normalize_embeddings=True)
    scores = util.cos_sim(embeddings[0], embeddings[1:])[0]
    best = int(scores.argmax())
    return float(scores[best]), accepted[best]


def meaning_check(answer, accepted, keywords=()):
    """Returns (same_meaning, best_match, score, reason)."""
    score, match = similarity(answer, accepted)
    if score < THRESHOLD:
        return False, match, score, "different meaning"
    if reason := fact_problem(answer, match, keywords):
        return False, match, score, reason
    return True, match, score, ""
