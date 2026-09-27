import json
from datetime import datetime
from types import SimpleNamespace

import pytest
import requests
from openpyxl import Workbook

from pipeline import mso_reserves
from pipeline.mso_reserves import parse_latest_reserves, build_reserves_json


HEADER = (
    "Obligation Date",
    "Stocks required under MSO (ML)",
    "Stock held under MSO (ML)",
    "Stock held under MSO (Days equivalent) [2]",
)


def _make_workbook(path, sheets):
    """sheets: {sheet_name: [(date, *values..., days), ...]} — mirrors the real
    DCCEEW layout: header row, fuel-name row, then one row per obligation date.
    Gasoline/Diesel carry an extra s16A column; Kerosene doesn't."""
    wb = Workbook()
    wb.remove(wb.active)
    wb.create_sheet("Title and index").append(["Minimum Stockholding Obligation - Weekly Snapshot"])
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        ws.append(HEADER)
        ws.append((None, name, name, name))
        for row in rows:
            ws.append(row)
    wb.save(path)
    return str(path)


def _standard_sheets(latest=datetime(2026, 9, 1)):
    return {
        "Gasoline": [
            (datetime(2026, 8, 25), 1067, 862, 1743, 41),
            (latest, 1067, 862, 1823, 43),
        ],
        "Diesel": [
            (datetime(2026, 8, 25), 2742, 2225, 3351, 36),
            (latest, 2742, 2225, 3039, 33),
        ],
        "Kerosene": [
            (datetime(2026, 8, 25), 663, 840, 31),
            (latest, 663, 901, 33),
        ],
    }


def test_parse_latest_reserves_reads_last_row_of_each_sheet(tmp_path):
    path = _make_workbook(tmp_path / "mso.xlsx", _standard_sheets())

    result = parse_latest_reserves(path)

    assert result["as_of"] == "2026-09-01"
    assert result["fuels"] == [
        {"key": "petrol", "label": "Petrol", "days": 43},
        {"key": "kerosene", "label": "Kerosene", "days": 33},
        {"key": "diesel", "label": "Diesel", "days": 33},
    ]


def test_parse_latest_reserves_ignores_trailing_blank_rows(tmp_path):
    sheets = _standard_sheets()
    sheets["Gasoline"].append((None, None, None, None, None))
    path = _make_workbook(tmp_path / "mso.xlsx", sheets)

    result = parse_latest_reserves(path)

    assert result["as_of"] == "2026-09-01"
    assert result["fuels"][0]["days"] == 43


def test_parse_latest_reserves_rejects_mismatched_dates(tmp_path):
    sheets = _standard_sheets()
    sheets["Kerosene"].pop()  # kerosene sheet lags a week
    path = _make_workbook(tmp_path / "mso.xlsx", sheets)

    with pytest.raises(ValueError, match="date"):
        parse_latest_reserves(path)


def test_parse_latest_reserves_rejects_non_numeric_days(tmp_path):
    sheets = _standard_sheets()
    sheets["Diesel"][-1] = (datetime(2026, 9, 1), 2742, 2225, 3039, "-")
    path = _make_workbook(tmp_path / "mso.xlsx", sheets)

    with pytest.raises(ValueError, match="Diesel"):
        parse_latest_reserves(path)


def test_parse_latest_reserves_rejects_implausible_days(tmp_path):
    sheets = _standard_sheets()
    sheets["Gasoline"][-1] = (datetime(2026, 9, 1), 1067, 862, 1823, 1823)
    path = _make_workbook(tmp_path / "mso.xlsx", sheets)

    with pytest.raises(ValueError, match="Gasoline"):
        parse_latest_reserves(path)


def test_parse_latest_reserves_rejects_missing_sheet(tmp_path):
    sheets = _standard_sheets()
    del sheets["Kerosene"]
    path = _make_workbook(tmp_path / "mso.xlsx", sheets)

    with pytest.raises(KeyError):
        parse_latest_reserves(path)


def test_build_reserves_json_matches_existing_file_shape():
    parsed = {
        "as_of": "2026-09-01",
        "fuels": [{"key": "petrol", "label": "Petrol", "days": 43}],
    }

    result = build_reserves_json(parsed)

    assert result == {
        "source": "DCCEEW Minimum Stockholding Obligation",
        "source_url": (
            "https://www.dcceew.gov.au/energy/security/australias-fuel-security/"
            "minimum-stockholding-obligation/statistics"
        ),
        "as_of": "2026-09-01",
        "fuels": [{"key": "petrol", "label": "Petrol", "days": 43}],
    }
    json.dumps(result)  # must be serialisable as-is


def test_download_spreadsheet_retries_after_read_timeout(tmp_path, monkeypatch):
    attempts = 0

    def fetch(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise requests.exceptions.ReadTimeout("DCCEEW stalled")
        return SimpleNamespace(content=b"workbook", raise_for_status=lambda: None)

    monkeypatch.setattr(mso_reserves.requests, "get", fetch)
    monkeypatch.setattr(mso_reserves, "sleep", lambda seconds: None, raising=False)
    path = tmp_path / "mso.xlsx"

    mso_reserves.download_spreadsheet(str(path))

    assert attempts == 2
    assert path.read_bytes() == b"workbook"


REPORT_TEXT = """Power BI Report
Minimum Stockholding Obligation (MSO) - Stocks held on 22/09/26
Last updated: 25/09/2026
Automotivegasoline
Aviationkerosene
Automotivediesel
1807
786
2938
Latest fuel stocks held under the Minimum Stockholding Obligation
Days of stocks at normal rate of consumption
Minimum Stockholding Obligation (ML)
MSO after reductions applied (ML)
Kerosene
Days
29
Above required
19%
Diesel
Days
32
Above required
32%
Gasoline
Days
42
Above required
110%
Current MSO after reductions applied
Gasoline*
862 ML
Kerosene
663 ML
Diesel*
2225 ML
"""


def test_parse_report_reserves_reads_public_day_cards():
    assert mso_reserves.parse_report_reserves(REPORT_TEXT) == {
        "as_of": "2026-09-22",
        "fuels": [
            {"key": "petrol", "label": "Petrol", "days": 42},
            {"key": "kerosene", "label": "Kerosene", "days": 29},
            {"key": "diesel", "label": "Diesel", "days": 32},
        ],
    }


def test_parse_report_reserves_rejects_missing_day_card():
    incomplete = REPORT_TEXT.replace("Diesel\nDays\n32\nAbove required\n32%\n", "")

    with pytest.raises(ValueError, match="Diesel"):
        mso_reserves.parse_report_reserves(incomplete)


def test_parse_report_reserves_rejects_implausible_days():
    incorrect = REPORT_TEXT.replace("Gasoline\nDays\n42", "Gasoline\nDays\n1807")

    with pytest.raises(ValueError, match="Gasoline"):
        mso_reserves.parse_report_reserves(incorrect)


def test_parse_report_reserves_rejects_missing_date():
    incomplete = REPORT_TEXT.replace("Stocks held on 22/09/26", "Stocks held on unavailable")

    with pytest.raises(ValueError, match="date"):
        mso_reserves.parse_report_reserves(incomplete)


def test_fetch_report_reserves_reads_browser_and_closes_it(monkeypatch):
    from selenium import webdriver

    class FakeBrowser:
        def __init__(self):
            self.closed = False

        def set_page_load_timeout(self, seconds):
            pass

        def get(self, url):
            assert url == mso_reserves.REPORT_URL

        def execute_script(self, script):
            assert script == "return document.body.innerText"
            return REPORT_TEXT

        def quit(self):
            self.closed = True

    browser = FakeBrowser()
    monkeypatch.setattr(webdriver, "Chrome", lambda options: browser)

    result = mso_reserves.fetch_report_reserves()

    assert result["as_of"] == "2026-09-22"
    assert result["fuels"][0]["days"] == 42
    assert browser.closed
