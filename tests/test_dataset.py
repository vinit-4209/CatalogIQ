import csv
from collections import Counter
from pathlib import Path

from app.services.dedup import calculate_content_hash, normalize_content


def test_sample_csv_exists_and_meets_row_requirements():
    csv_path = Path(__file__).resolve().parent.parent / "data" / "sample_products.csv"
    assert csv_path.exists(), f"Sample CSV file not found at {csv_path}"

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    # Verify columns exactly match
    assert fieldnames == ["sku", "raw_title", "raw_description"]

    # Verify >= 200 rows
    assert len(rows) >= 200, f"Expected at least 200 rows, found {len(rows)}"

    # Verify no empty skus or raw_titles
    for idx, row in enumerate(rows, start=2):
        assert row["sku"].strip(), f"Row {idx} has empty SKU"
        assert row["raw_title"].strip(), f"Row {idx} has empty raw_title"


def test_sample_csv_contains_intentional_duplicates():
    csv_path = Path(__file__).resolve().parent.parent / "data" / "sample_products.csv"
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Compute content hashes using the exact assignment normalization rule
    hashes = [
        calculate_content_hash(r["raw_title"], r["raw_description"])
        for r in rows
    ]
    hash_counts = Counter(hashes)

    # Duplicate hashes (hashes that appear > 1 time)
    duplicate_hashes = {h: count for h, count in hash_counts.items() if count > 1}

    # Verify there are intentional duplicates
    assert len(duplicate_hashes) >= 10, (
        f"Expected at least 10 duplicate groups, found {len(duplicate_hashes)}"
    )

    # Verify that duplicate listings have distinct SKUs
    skus_by_hash = {}
    for r in rows:
        h = calculate_content_hash(r["raw_title"], r["raw_description"])
        skus_by_hash.setdefault(h, []).append(r["sku"])

    for h, skus in skus_by_hash.items():
        if len(skus) > 1:
            assert len(skus) == len(set(skus)), f"Duplicate SKUs found for hash {h}: {skus}"


def test_sample_csv_normalization_handles_whitespace_and_casing():
    csv_path = Path(__file__).resolve().parent.parent / "data" / "sample_products.csv"
    with open(csv_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # Find at least one pair where raw text differs in casing or whitespace but normalizes to identical string
    found_casing_or_whitespace_variant = False

    hash_to_rows = {}
    for r in rows:
        h = calculate_content_hash(r["raw_title"], r["raw_description"])
        hash_to_rows.setdefault(h, []).append(r)

    for h, matches in hash_to_rows.items():
        if len(matches) > 1:
            title_a = matches[0]["raw_title"]
            title_b = matches[1]["raw_title"]
            if title_a != title_b:
                assert normalize_content(title_a) == normalize_content(title_b)
                found_casing_or_whitespace_variant = True
                break

    assert found_casing_or_whitespace_variant, (
        "Expected to find duplicate pairs with varied casing/whitespace in sample dataset"
    )
