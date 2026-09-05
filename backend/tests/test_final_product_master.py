from decimal import Decimal
import inspect

import pytest

from app.scripts import import_final_catalog
from app.scripts.import_final_catalog import CATEGORY_CODES, SERIES_CODES, CatalogRow, load_catalog


def test_final_seed_count_and_unique_identity():
    rows = load_catalog()
    assert len(rows) == 160
    assert len({row.identity for row in rows}) == 160


def test_exact_category_and_series_structure():
    rows = load_catalog()
    assert {row.category for row in rows} == set(CATEGORY_CODES)
    assert {row.series for row in rows} == set(SERIES_CODES)
    assert len(CATEGORY_CODES) == 7
    assert len(SERIES_CODES) == 12


def test_prices_are_present_and_client_values_are_preserved():
    rows = load_catalog()
    prices = {(row.series, row.product, row.variant): row.price for row in rows}
    assert all(row.price > 0 for row in rows)
    assert prices[("Naruto", "Naruto Rasengan", None)] == Decimal("800")
    assert prices[("One Piece", "Luffy Sitting", "Variant 1")] == Decimal("400")
    assert prices[("One Piece", "Luffy Sitting", "Variant 2")] == Decimal("800")
    assert prices[("Dragon Ball Z", "Goku Standing", "Variant 2")] == Decimal("2200")
    assert prices[("Jujutsu Kaisen", "Gojo Standing", "Variant 2")] == Decimal("2500")


def test_missing_price_is_rejected(tmp_path):
    source = tmp_path / "bad.csv"
    source.write_text("category,series,product,variant,price\nAction Figures,Naruto,Test,-,\n")
    with pytest.raises(ValueError, match="Missing required"):
        load_catalog(source)


def test_keychains_are_only_generic_masters():
    rows = [row for row in load_catalog() if row.category == "Keychains"]
    assert [(row.series, row.product, row.price) for row in rows] == [
        ("Generic Types", "Rubber Keychain", Decimal("100")),
        ("Generic Types", "Metal Keychain", Decimal("100")),
        ("Generic Types", "Keyboard Keychain", Decimal("200")),
    ]


def test_all_princess_superhero_qposkets_are_400():
    rows = [row for row in load_catalog() if row.category == "Qposket Figures"]
    assert len(rows) == 11
    assert {row.price for row in rows} == {Decimal("400")}


@pytest.mark.parametrize("name,count", [("Luffy Sitting", 3), ("Gojo Standing", 2), ("Goku Standing", 2), ("Deadpool", 2), ("Pokemon Set of 6", 2)])
def test_duplicate_name_variants_remain_distinct(name, count):
    rows = [row for row in load_catalog() if row.product == name]
    assert len(rows) == count
    assert len({row.identity for row in rows}) == count
    assert len({row.import_reference for row in rows}) == count
    assert all(row.variant and row.display_name.endswith(row.variant) for row in rows)


def test_import_keys_are_deterministic_for_idempotency():
    first = CatalogRow("Action Figures", "Naruto", "Naruto Rasengan", None, Decimal("800"))
    second = CatalogRow("Action Figures", "Naruto", "Naruto Rasengan", None, Decimal("999"))
    assert first.import_reference == second.import_reference


def test_cleanup_uses_soft_delete_for_historical_fk_safety():
    source = inspect.getsource(import_final_catalog.import_catalog)
    assert "product.status, product.deleted_at" in source
    assert "session.delete" not in source
    assert "TRUNCATE" not in source.upper()
