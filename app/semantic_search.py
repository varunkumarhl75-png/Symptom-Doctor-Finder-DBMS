from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

MODEL = None


def get_model():
    """Load the embedding model once and reuse it across requests."""
    global MODEL
    if MODEL is None:
        MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return MODEL


def find_best_symptom(user_text, stored_symptoms):
    if not stored_symptoms:
        return {"index": -1, "similarity": 0.0}

    model = get_model()
    user_embedding = model.encode([user_text], convert_to_numpy=True)
    symptom_embeddings = model.encode(stored_symptoms, convert_to_numpy=True)

    similarities = cosine_similarity(user_embedding, symptom_embeddings)[0]
    best_index = int(similarities.argmax())

    return {
        "index": int(best_index),
        "similarity": float(similarities[best_index])
    }


def find_best_matches(user_text, stored_symptoms, top_n=5):
    if not stored_symptoms:
        return []

    model = get_model()
    user_embedding = model.encode([user_text], convert_to_numpy=True)
    symptom_embeddings = model.encode(stored_symptoms, convert_to_numpy=True)
    similarities = cosine_similarity(user_embedding, symptom_embeddings)[0]

    ranked = [
        {"index": int(index), "similarity": float(score)}
        for index, score in enumerate(similarities)
    ]
    ranked.sort(key=lambda item: item["similarity"], reverse=True)

    return ranked[:top_n]