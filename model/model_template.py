from threads.label_classifier import get_top_labels


if __name__ == "__main__":
    title = "If you want to become a quant dev here are the steps you should take"
    description = "This is a practical guide to learning quant roles and market microstructure."

    top_labels = get_top_labels(title, description, top_n=10)

    for tag in top_labels:
        print(f"{tag['rank']}. {tag['label']} ({tag['id']}): {tag['score']:.4f}")
