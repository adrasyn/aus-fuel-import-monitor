"""Read DCCEEW MSO days-equivalent data into mso-reserves.json."""

from datetime import datetime
import re
from time import sleep

import requests
from openpyxl import load_workbook

SPREADSHEET_URL = (
    "https://www.dcceew.gov.au/sites/default/files/documents/"
    "mso-weekly-snapshot-timeseries.xlsx"
)
SOURCE_URL = (
    "https://www.dcceew.gov.au/energy/security/australias-fuel-security/"
    "minimum-stockholding-obligation/statistics"
)
REPORT_URL = (
    "https://app.powerbi.com/view?"
    "r=eyJrIjoiMzcyZmE4ZjgtOGRjNy00NGM3LWExYTktMTk2NzU2NWEzNzkzIiw"
    "idCI6IjhjM2M4MWJjLTJiM2MtNDRhZi1iM2Y3LTZmNjIwYjM5MTBlZSJ9"
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


def parse_report_reserves(content: str) -> dict:
    """Read the dated days-equivalent cards from DCCEEW's public report."""
    date_match = re.search(
        r"Minimum Stockholding Obligation \(MSO\) - Stocks held on (\d{2}/\d{2}/\d{2})",
        content,
    )
    if date_match is None:
        raise ValueError("report date missing")
    as_of = datetime.strptime(date_match.group(1), "%d/%m/%y").date().isoformat()

    marker = "Days of stocks at normal rate of consumption"
    if marker not in content or "Current MSO after reductions applied" not in content:
        raise ValueError("report days-equivalent section missing")
    section = content.split(marker, 1)[1].split("Current MSO after reductions applied", 1)[0]
    fuels = []
    for sheet, key, label in FUEL_SHEETS:
        matches = re.findall(rf"(?m)^{sheet}\s+Days\s+(\d+)\s+Above required", section)
        if len(matches) != 1:
            raise ValueError(f"{sheet}: expected one days-equivalent card")
        days = int(matches[0])
        if not MIN_DAYS <= days <= MAX_DAYS:
            raise ValueError(f"{sheet}: implausible days value {days}")
        fuels.append({"key": key, "label": label, "days": days})
    return {"as_of": as_of, "fuels": fuels}


def fetch_report_reserves() -> dict:
    """Read the public report in Chrome (the workbook blocks cloud runners)."""
    from selenium import webdriver
    from selenium.webdriver.support.ui import WebDriverWait

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1440,1100")
    driver = webdriver.Chrome(options=options)
    try:
        driver.set_page_load_timeout(60)
        driver.get(REPORT_URL)

        def loaded_text(browser):
            content = browser.execute_script("return document.body.innerText") or ""
            return content if all(
                re.search(rf"(?m)^{sheet}\s+Days\s+\d+\s+Above required", content)
                for sheet, _, _ in FUEL_SHEETS
            ) else False

        return parse_report_reserves(WebDriverWait(driver, 90).until(loaded_text))
    finally:
        driver.quit()


def build_reserves_json(parsed: dict) -> dict:
    return {
        "source": "DCCEEW Minimum Stockholding Obligation",
        "source_url": SOURCE_URL,
        "as_of": parsed["as_of"],
        "fuels": parsed["fuels"],
    }
