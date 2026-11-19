from cache import (
    get_cached_json,
    normalize_symptom_query,
    set_cached_json
)
from semantic_search import find_best_symptom


def query_symptom_match(cursor, symptoms):
    cursor.execute(
        "SELECT search_id, symptom_text FROM symptom_search ORDER BY search_id"
    )
    symptom_rows = cursor.fetchall()
    if not symptom_rows:
        return {"status": "no_symptoms"}

    stored_symptoms = [row["symptom_text"] for row in symptom_rows]
    best_match = find_best_symptom(symptoms, stored_symptoms)
    if best_match["index"] < 0 or best_match["similarity"] < 0.2:
        return {"status": "no_match"}

    matched_symptom = symptom_rows[best_match["index"]]
    return {
        "status": "matched",
        "search_id": matched_symptom["search_id"],
        "matched_symptom": matched_symptom["symptom_text"],
        "similarity_score": float(best_match["similarity"])
    }


def get_symptom_match(cursor, symptoms):
    parameters = {"query": normalize_symptom_query(symptoms)}
    cached = get_cached_json("symptom_search", parameters)
    if cached is not None:
        return cached

    result = query_symptom_match(cursor, symptoms)
    if result["status"] == "matched":
        set_cached_json("symptom_search", parameters, result)
    return result


def query_doctor_groups(cursor, search_id):
    cursor.execute(
        """
            SELECT
                sp.name AS specialization,
                ss2.similarity_score,
                d.doctor_id,
                d.name AS doctor_name,
                d.qualification,
                d.experience_years,
                c.name AS clinic_name,
                d.phone
            FROM symptom_specialization ss2
            JOIN specialization sp
                ON ss2.specialization_id = sp.specialization_id
            JOIN doctor d
                ON d.specialization_id = sp.specialization_id
            JOIN clinic c
                ON d.clinic_id = c.clinic_id
            WHERE ss2.search_id = %s
            ORDER BY ss2.similarity_score DESC, d.experience_years DESC
        """,
        (search_id,)
    )
    results = cursor.fetchall()

    grouped_results = {}
    for row in results:
        specialization_name = row["specialization"]
        if specialization_name not in grouped_results:
            grouped_results[specialization_name] = {
                "specialization": specialization_name,
                "similarity_score": float(row["similarity_score"]),
                "doctors": []
            }

        grouped_results[specialization_name]["doctors"].append({
            "doctor_id": row["doctor_id"],
            "doctor_name": row["doctor_name"],
            "qualification": row["qualification"],
            "experience_years": row["experience_years"],
            "clinic_name": row["clinic_name"],
            "phone": row["phone"]
        })

    return sorted(
        grouped_results.values(),
        key=lambda group: group["similarity_score"],
        reverse=True
    )


def get_doctor_groups(cursor, search_id):
    parameters = {"search_id": search_id}
    cached = get_cached_json("doctor_search", parameters)
    if cached is not None:
        return cached

    groups = query_doctor_groups(cursor, search_id)
    set_cached_json("doctor_search", parameters, groups)
    return groups
