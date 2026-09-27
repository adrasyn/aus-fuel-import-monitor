"""Parse the DCCEEW MSO weekly snapshot spreadsheet into mso-reserves.json."""

from datetime import datetime
import re
from time import sleep

import requests
from openpyxl import load_workbook

SPREADSHEET_URL = (
    "https://www.dcceew.gov.au/sites/default/files/documents/"
    "mso-weekly-snapshot-timeseries.xlsx"
)
READER_URL = f"https://r.jina.ai/{SPREADSHEET_URL}"
SOURCE_URL = (
    "https://www.dcceew.gov.au/energy/security/australias-fuel-security/"
    "minimum-stockholding-obligation/statistics"
)

# (sheet name in workbook, key/label used by the site). Order is render order.
FUEL_SHEETS = [
    ("Gasoline", "petrol", "Petrol"),
    ("Kerosene", "kerosene", "Kerosene"),
    ("Diesel", "diesel", "Diesel"),
]

# Sanity bounds on "days equivalent" — guards against picking up a volume
# column (hundreds/thousands of ML) if the sheet layout shifts.
MIN_DAYS, MAX_DAYS = 10, 90


def download_spreadsheet(output_path: str) -> str:
    for attempt in range(3):
        try:
            resp = requests.get(SPREADSHEET_URL, timeout=(10, 120))
            resp.raise_for_status()
            break
        except requests.exceptions.Timeout:
            if attempt == 2:
                raise
            sleep(2 ** attempt)
    with open(output_path, "wb") as f:
        f.write(resp.content)
    return output_path


def _latest_row(ws) -> tuple:
    """Last row whose first cell is an obligation date. Days equivalent is
    always the final column, whether or not the sheet has the s16A column."""
    latest = None
    for row in ws.iter_rows(min_row=3, values_only=True):
        if isinstance(row[0], datetime):
            latest = row
    if latest is None:
        raise ValueError(f"{ws.title}: no dated rows found")
    return latest


def parse_latest_reserves(excel_path: str) -> dict:
    wb = load_workbook(excel_path, read_only=True, data_only=True)
    as_of = None
    fuels = []
    for sheet, key, label in FUEL_SHEETS:
        row = _latest_row(wb[sheet])
        date = row[0].date().isoformat()
        if as_of is None:
            as_of = date
        elif date != as_of:
            raise ValueError(f"{sheet}: latest date {date} != {as_of}")
        days = row[-1]
        if not isinstance(days, int) or not MIN_DAYS <= days <= MAX_DAYS:
            raise ValueError(f"{sheet}: implausible days value {days!r}")
        fuels.append({"key": key, "label": label, "days": days})
    return {"as_of": as_of, "fuels": fuels}


def parse_reader_reserves(content: str) -> dict:
    """Read Jina's text conversion of the DCCEEW workbook."""
    if f"URL Source: {SPREADSHEET_URL}" not in content:
        raise ValueError("reader response is not the DCCEEW MSO workbook")

    as_of = None
    fuels = []
    for sheet, key, label in FUEL_SHEETS:
        heading = re.search(rf"(?m)^# \[Sheet \d+: _{sheet}_\]", content)
        if heading is None:
            raise ValueError(f"{sheet}: missing from reader response")
        section = content[heading.end():]
        next_heading = re.search(r"(?m)^# \[Sheet \d+:", section)
        if next_heading:
            section = section[:next_heading.start()]
        if "Stock held under MSO (Days equivalent)" not in section:
            raise ValueError(f"{sheet}: days-equivalent column missing")

        rows = re.findall(r"(?m)^\*\*(\d{1,2}/\d{1,2}/\d{4})\*\*(.*)$", section)
        if not rows:
            raise ValueError(f"{sheet}: no dated rows found")
        date_text, values_text = max(rows, key=lambda row: datetime.strptime(row[0], "%m/%d/%Y"))
        date = datetime.strptime(date_text, "%m/%d/%Y").date().isoformat()
        if as_of is None:
            as_of = date
        elif date != as_of:
            raise ValueError(f"{sheet}: latest date {date} != {as_of}")

        values = values_text.strip().split()
        expected_count = 3 if sheet == "Kerosene" else 4
        if len(values) != expected_count or not all(value.isdecimal() for value in values):
            raise ValueError(f"{sheet}: malformed latest row {values_text!r}")
        days = int(values[-1])
        if not MIN_DAYS <= days <= MAX_DAYS:
            raise ValueError(f"{sheet}: implausible days value {days}")
        fuels.append({"key": key, "label": label, "days": days})
    return {"as_of": as_of, "fuels": fuels}


def fetch_reader_reserves() -> dict:
    """Fetch the public workbook through its text reader from GitHub runners."""
    for attempt in range(3):
        try:
            resp = requests.get(READER_URL, headers={"X-No-Cache": "true"}, timeout=(10, 60))
            resp.raise_for_status()
            return parse_reader_reserves(resp.text)
        except (requests.exceptions.RequestException, ValueError):
            if attempt == 2:
                raise
            sleep(2 ** attempt)


def build_reserves_json(parsed: dict) -> dict:
    return {
        "source": "DCCEEW Minimum Stockholding Obligation",
        "source_url": SOURCE_URL,
        "as_of": parsed["as_of"],
        "fuels": parsed["fuels"],
    }
