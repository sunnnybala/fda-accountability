# /// script
# requires-python = ">=3.10"
# dependencies = ["openpyxl"]
# ///
"""Build the FDA Accountability dashboard.

Reads the FDA's own spreadsheet of novel drug approvals and its published
rejection letters, then writes:

  data/drugs.json   one record per drug (the open data file)
                    including the human-cost inputs from data/human_cost.json
  docs/index.html   the dashboard, a single self-contained page

Run from the project root:

  uv run scripts/build.py               # rebuild from the files in data/raw
  uv run scripts/build.py --refresh-crl # also re-download the rejection letters
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import re
import statistics
import urllib.request
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
XLSX = ROOT / "data" / "raw" / "fda-novel-drug-approvals.xlsx"
CRL = ROOT / "data" / "raw" / "fda-rejection-letters.json"
HUMAN_COST = ROOT / "data" / "human_cost.json"
TEMPLATE = ROOT / "scripts" / "template.html"
OUT_JSON = ROOT / "data" / "drugs.json"
OUT_HTML = ROOT / "docs" / "index.html"

FIRST_YEAR = 2020
XLSX_SOURCE = "https://www.fda.gov/media/177921/download?attachment"
CRL_SOURCE = "https://api.fda.gov/transparency/crl.json"
NO_BRAND = "[drug marketed without a proprietary name]"


def as_date(value) -> dt.date | None:
    """The spreadsheet stores older dates as dates and newer ones as text."""
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
            try:
                return dt.datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                pass
    return None


def clean(value) -> str:
    return re.sub(r"[ \t]+", " ", str(value or "")).strip()


def yes(value) -> bool:
    return clean(value).lower().startswith("yes")


def approved_for(label_text: str) -> str:
    """Shorten the label's 'indicated for ...' sentence to one line."""
    text = re.sub(r"\s+", " ", label_text).strip()
    match = re.search(
        r"indicated\s*:?\s*(.*?)(?:\.\s|\.$|;| Limitations| This indication| •|$)",
        text,
        re.I,
    )
    phrase = (match.group(1) if match else text).strip(" :,-")
    if len(phrase) > 150:
        phrase = phrase[:150].rsplit(" ", 1)[0].rstrip(" ,(") + "…"
    return phrase


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def refresh_crl() -> None:
    """Download the rejection letters and keep only the fields we use."""
    req = urllib.request.Request(
        CRL_SOURCE + "?limit=1000", headers={"User-Agent": "fda-accountability-build"}
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        results = json.load(resp)["results"]
    keep = ("application_number", "letter_date", "letter_type", "approval_status", "file_name")
    slim = [{k: r.get(k) for k in keep} for r in results]
    CRL.write_text(
        json.dumps(
            {"source": CRL_SOURCE, "downloaded": dt.date.today().isoformat(), "letters": slim},
            indent=1,
        )
    )


def load_rejections() -> dict[str, list[str]]:
    """Application number -> sorted dates of 'complete response' (rejection) letters."""
    by_app: dict[str, set[str]] = collections.defaultdict(set)
    for letter in json.loads(CRL.read_text())["letters"]:
        kind = letter.get("letter_type")
        # Letters from before 2008 carry no type; they are the older
        # "not approvable" letters, filed with the other action letters.
        untyped_old = kind is None and "OtherActionLtrs" in str(letter.get("file_name"))
        if kind != "COMPLETE RESPONSE" and not untyped_old:
            continue
        date = as_date(letter.get("letter_date"))
        if not date:
            continue
        for number in re.findall(r"\d{6}", str(letter.get("application_number") or "")):
            by_app[number].add(date.isoformat())
    return {k: sorted(v) for k, v in by_app.items()}


def load_human_cost() -> dict[str, dict]:
    """Hand-checked inputs for the human cost, keyed by drug id.

    Each entry gives the survival gain a randomised trial measured and the
    number of people in the US who become eligible for the drug each year,
    with a source for both. The page multiplies them by the wait.
    """
    if not HUMAN_COST.exists():
        return {}
    out = {}
    for drug_id, c in json.loads(HUMAN_COST.read_text())["drugs"].items():
        gain = c.get("gain_months")
        if gain is None:
            gain = round(c["os_drug_months"] - c["os_control_months"], 1)
        if gain <= 0 or c["us_eligible_per_year"] <= 0:
            raise SystemExit(f"human_cost.json: {drug_id} has no positive gain or patient count")
        out[drug_id] = {
            "trial": c["trial"],
            "os_drug_months": c.get("os_drug_months"),
            "os_control_months": c.get("os_control_months"),
            "gain_months": gain,
            "gain_source": c["os_source"],
            "eligible_per_year": c["us_eligible_per_year"],
            "eligible_basis": c["eligible_basis"],
            "eligible_sources": c["eligible_sources"],
            "note": c.get("note", ""),
        }
    return out


def load_drugs() -> list[dict]:
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    rows = list(wb[wb.sheetnames[0]].iter_rows(values_only=True))
    header = [clean(c) for c in rows[0]]
    header = [re.sub(r"\s+", " ", h) for h in header]
    rejections = load_rejections()
    human_cost = load_human_cost()

    drugs, used_ids = [], set()
    for raw in rows[1:]:
        if not raw or not any(raw):
            continue
        row = dict(zip(header, raw))
        received = as_date(row["FDA Receipt Date"])
        approved = as_date(row["FDA Approval Date"])
        if not received or not approved or approved.year < FIRST_YEAR:
            continue

        ingredient = clean(row["Active Ingredient/Moiety"])
        brand = clean(row["Proprietary Name"])
        name = ingredient if brand == NO_BRAND or not brand else brand
        app_numbers = [
            clean(row[k]).zfill(6)
            for k in ("Application Number(1)", "Application Number(2)", "Application Number(3)")
            if row.get(k)
        ]
        letters = sorted({d for n in app_numbers for d in rejections.get(n, [])})
        # Only letters sent while this application was under review count.
        letters = [d for d in letters if received.isoformat() <= d <= approved.isoformat()]

        slug = base = slugify(name)
        n = 2
        while slug in used_ids:
            slug, n = f"{base}-{n}", n + 1
        used_ids.add(slug)

        use = clean(row["Approved Use(s)"])
        review = clean(row["Review Designation"])
        drugs.append(
            {
                "id": slug,
                "name": name,
                "ingredient": ingredient,
                "company": clean(row["Applicant"]),
                "application": f"{clean(row['NDA/BLA'])} {app_numbers[0]}",
                "received": received.isoformat(),
                "approved": approved.isoformat(),
                "days_at_fda": (approved - received).days,
                "approved_for": approved_for(use),
                "approved_use": use,
                "priority": review.lower().startswith("priority"),
                "orphan": yes(row["Orphan Drug Designation"]),
                "breakthrough": yes(row["Breakthrough Therapy Designation"]),
                "accelerated": yes(row["Accelerated Approval"]),
                "fast_track": yes(row["Fast Track Designation"]),
                "rejection_letters": letters,
                "fda_url": "https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm"
                f"?event=overview.process&ApplNo={app_numbers[0]}",
                "cost": human_cost.get(slug),
            }
        )
    missing = set(human_cost) - used_ids
    if missing:
        raise SystemExit(f"human_cost.json names drugs that are not in the FDA data: {sorted(missing)}")
    drugs.sort(key=lambda d: -d["days_at_fda"])
    return drugs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--refresh-crl", action="store_true", help="re-download rejection letters")
    args = parser.parse_args()
    if args.refresh_crl or not CRL.exists():
        refresh_crl()

    drugs = load_drugs()
    days = [d["days_at_fda"] for d in drugs]
    payload = {
        "meta": {
            "built": dt.date.today().isoformat(),
            "first_year": FIRST_YEAR,
            "last_approval": max(d["approved"] for d in drugs),
            "count": len(drugs),
            "sources": {"approvals": XLSX_SOURCE, "rejection_letters": CRL_SOURCE},
        },
        "drugs": drugs,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n")

    inline = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = TEMPLATE.read_text().replace("/*__DATA__*/null", inline)
    OUT_HTML.write_text(html)

    priority = [d["days_at_fda"] for d in drugs if d["priority"]]
    print(f"{len(drugs)} drugs approved {FIRST_YEAR} to {payload['meta']['last_approval']}")
    print(f"median days at FDA: {statistics.median(days)}  shortest: {min(days)}  longest: {max(days)}")
    print(f"priority drugs: {len(priority)}, median {statistics.median(priority)} days")
    print(f"with a rejection letter on file: {sum(1 for d in drugs if d['rejection_letters'])}")
    for bench in (21, 30, 60):
        beyond = sum(max(0, x - bench) for x in days)
        within = sum(1 for x in days if x <= bench)
        print(f"benchmark {bench}: {within} within, {beyond:,} days beyond ({beyond / 365.25:.0f} years)")
    costed = [d for d in drugs if d["cost"]]
    if costed:
        print(f"human cost counted for {len(costed)} drugs, at a 60-day benchmark:")
        total_p = total_y = 0.0
        for d in sorted(costed, key=lambda d: d["name"]):
            c = d["cost"]
            patients = c["eligible_per_year"] * max(0, d["days_at_fda"] - 60) / 365.25
            years = patients * c["gain_months"] / 12
            total_p, total_y = total_p + patients, total_y + years
            print(f"  {d['name']:<10} {c['eligible_per_year']:>7,}/yr x {d['days_at_fda'] - 60:>4} d x {c['gain_months']:>4} mo"
                  f" = {patients:>8,.0f} patients, {years:>8,.0f} life-years")
        print(f"  total: {total_p:,.0f} patients, {total_y:,.0f} life-years")
    print(f"wrote {OUT_JSON.relative_to(ROOT)} and {OUT_HTML.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
