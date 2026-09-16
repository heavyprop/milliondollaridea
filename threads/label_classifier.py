from pathlib import Path

from sentence_transformers import SentenceTransformer, util

MODEL_NAME = "sentence-transformers/paraphrase-MiniLM-L3-v2"
TAXONOMY_PATH = Path(__file__).resolve().parent.parent / "model" / "tags" / "content_taxonomy_3_1.tsv"


def load_taxonomy():
    labels = []

    with TAXONOMY_PATH.open("r", encoding="utf-8") as file:
        next(file, None)

        for line in file:
            parts = line.rstrip("\n").split("\t")

            if len(parts) >= 3 and parts[0] and parts[2]:
                labels.append({
                    "id": parts[0],
                    "label": parts[2],
                })

    return labels

model = SentenceTransformer(MODEL_NAME)
taxonomy = load_taxonomy()
label_names = [item["label"] for item in taxonomy]
label_embeddings = model.encode(label_names)

def get_top_labels(title, description=None, top_n=10):
    title = (title or "").strip()
    has_description = description is not None and description.strip()

    if has_description:
        text = f"{title} [SEP] {description.strip()}"
    else:
        text = title

    text_embedding = model.encode(text)

    scores = util.cos_sim(text_embedding, label_embeddings)[0]
    ranked = sorted(
        zip(taxonomy, scores.tolist()),
        key=lambda item: item[1],
        reverse=True,
    )

    return [
        {
            "id": label["id"],
            "label": label["label"],
            "score": float(max(0.0, score)),
            "rank": rank,
        }
        for rank, (label, score) in enumerate(ranked[:top_n], start=1)
    ]
