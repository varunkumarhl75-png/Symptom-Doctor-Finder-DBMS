from semantic_search import find_best_matches, find_best_symptom


def test_find_best_symptom():
    stored_symptoms = [
        "I have been experiencing chest pain and shortness of breath when walking.",
        "I have severe headaches along with dizziness and occasional blurred vision.",
        "I have persistent pain around my knee after exercising."
    ]

    user_text = "My chest feels tight and I become breathless when walking."
    result = find_best_symptom(user_text, stored_symptoms)

    assert result["index"] == 0, "The chest-related symptom should rank first."
    assert result["similarity"] > 0.6, "Similarity should be strong for a clear semantic match."


def test_find_best_matches():
    stored_symptoms = [
        "I have been experiencing chest pain and shortness of breath when walking.",
        "I have severe headaches along with dizziness and occasional blurred vision.",
        "I have persistent pain around my knee after exercising.",
        "I need medical advice related to pregnancy and regular checkups."
    ]

    user_text = "I have frequent headaches and difficulty concentrating."
    matches = find_best_matches(user_text, stored_symptoms, top_n=3)

    assert len(matches) == 3, "A ranked top-list should be returned."
    assert matches[0]["similarity"] >= matches[1]["similarity"], "Results should be sorted descending."
    assert matches[0]["index"] in {1, 3}, "Headache-related symptoms should rank highest."


if __name__ == "__main__":
    test_find_best_symptom()
    test_find_best_matches()
    print("Semantic search regression tests passed.")