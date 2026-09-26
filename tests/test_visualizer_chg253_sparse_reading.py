from __future__ import annotations

from scripts.release_checks.run_chg253_sparse_reading_acceptance import run_acceptance


def test_native_preview_fits_sparse_content_and_preserves_chg207_reading(tmp_path) -> None:
    receipt = run_acceptance(tmp_path)

    assert receipt["status"] == "PASS"
    assert set(receipt["sparse_matrix"]) == {"320", "359", "360", "361", "389", "390", "391", "1440"}
    assert receipt["sparse_matrix"]["390"]["table"]["body"]["scrollHeight"] <= receipt["sparse_matrix"]["390"]["table"]["body"]["clientHeight"] + 1
    assert receipt["table_interaction"]["focusRetained"] is True
    assert receipt["source_data_unchanged"] is True
