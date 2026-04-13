import os
import pytest
from pipeline.petroleum_stats import parse_imports_sheet, parse_consumption_cover

EXCEL_PATH = r"C:\Users\wilso\Downloads\aus-petroleum-stats-jan-2026.xlsx"

@pytest.mark.skipif(not os.path.exists(EXCEL_PATH), reason="Excel file not available")
def test_parse_imports_sheet():
    records = parse_imports_sheet(EXCEL_PATH)
    assert len(records) > 100
    first = records[0]
    assert "month" in first
    assert "crude_oil_ml" in first
    assert "diesel_ml" in first
    assert "gasoline_ml" in first
    assert "jet_fuel_ml" in first
    assert "fuel_oil_ml" in first
    assert "lpg_ml" in first
    assert "total_ml" in first

@pytest.mark.skipif(not os.path.exists(EXCEL_PATH), reason="Excel file not available")
def test_parse_consumption_cover():
    records = parse_consumption_cover(EXCEL_PATH)
    assert len(records) > 100
    last = records[-1]
    assert "month" in last
    assert "total_days" in last
    assert last["total_days"] > 0
