# FDA Accountability

A public dashboard of how long every new drug waited at the FDA, and what that wait cost patients.

**Live site: https://sunnnybala.github.io/fda-accountability/**

The public scrutinizes the harm from approving a drug. The harm from withholding a useful one is much less visible. This project makes it visible, using the FDA's own records.

## What the dashboard shows

It covers every novel drug the FDA's drug centre approved from 2020 through 2025: 291 drugs.

For each drug:

| Number | What it means |
|---|---|
| **Filed** | The day the FDA received the company's application. |
| **Approved** | The day the FDA approved the drug. |
| **Days at the FDA** | The days between those two dates. The clock never pauses. |
| **Days beyond** | Days at the FDA minus the benchmark. This is the wait the dashboard counts. |
| **Rejected first** | The FDA has published a rejection letter for this application dated between filing and approval. The time after a rejection still counts. |
| **Priority, Rare disease** | Designations the FDA itself gave the drug. Priority means the FDA judged it a significant improvement for a serious condition. |

For 12 cancer drugs it also shows the human cost:

| Number | What it means |
|---|---|
| **Patients** | People in the US who became eligible for the drug during the days beyond the benchmark. |
| **Years of life at stake** | Those patients, times the extra time patients lived on the drug in its randomised trial. |

### The benchmark

Every drug is measured against a fast review instead of the FDA's usual deadline. You can switch between three:

- **60 days.** The FDA's national priority voucher programme targets a review of one to two months after submission, against the usual 10 to 12. If that can be the target for those drugs, the deadline for the rest is a choice.
- **30 days.** A target, not a record. What a very competent agency would aim for.
- **21 days.** In December 2020 the first COVID-19 vaccine was authorised for emergency use 21 days after the request was filed.

No drug in the data was approved within 60 days. The fastest took 61.

## Where the data comes from

Everything is public. Nothing is scraped from behind a login or a paywall.

### 1. Filing dates, approval dates and designations

- **Source:** the FDA's "Compilation of CDER New Molecular Entity (NME) Drug and New Biologic Approvals", a spreadsheet the FDA publishes.
- **Link:** https://www.fda.gov/media/177921/download?attachment
- **Copy in this repo:** `data/raw/fda-novel-drug-approvals.xlsx`
- **Fields used:** proprietary name, active ingredient, applicant, application number, FDA receipt date, FDA approval date, approved use, review designation, orphan, breakthrough, accelerated approval and fast track flags.
- **Coverage:** 1,387 drugs from 1985 to December 30, 2025. The dashboard uses the 291 approved since 2020.
- **Updates:** the FDA refreshes it about once a year.

### 2. Rejection letters

- **Source:** openFDA's database of complete response letters, the letters the FDA sends when it declines to approve an application.
- **Link:** https://api.fda.gov/transparency/crl.json
- **Copy in this repo:** `data/raw/fda-rejection-letters.json` (the letter text is dropped; only the application number, date and type are kept).
- **How it is used:** a letter is matched to a drug by application number. 50 of the 291 drugs have at least one.
- **Gap:** the FDA has not published every letter, so some long waits include a rejection that is not labelled.

### 3. Human cost inputs

- **File:** `data/human_cost.json`, written by hand for this project.
- **For each of the 12 drugs it holds:**
  - the median survival with and without the drug in a randomised trial, with a link and a quote. These come from the FDA-approved label or the published trial.
  - the number of people in the US who become eligible each year, with a link and a quote for every figure used. These come from company annual reports and investor filings, FDA review documents, American Cancer Society statistics and peer-reviewed studies.
- **Quality varies and each entry says so.** Four patient counts are stated directly by a source, six are worked out from sourced pieces, and two are rough estimates.
- **Left out:** five drugs that were researched but not counted, each with its reason, are listed in the same file under `left_out`.

### The record link on each drug

Each drug links to its page on Drugs@FDA, the FDA's own database: `https://www.accessdata.fda.gov/scripts/cder/daf/`.

## How the human cost is calculated

```
patients       = people who become eligible per year × (days beyond the benchmark ÷ 365.25)
years of life  = patients × (median survival with the drug − median survival without it)
```

Example, Vanflyta for acute myeloid leukemia, at the 60-day benchmark:

- About 2,850 people in the US become eligible each year.
- It spent 330 days at the FDA, 270 beyond the benchmark. In that time about 2,100 patients became eligible.
- In the QuANTUM-First trial patients lived a median of 31.9 months with the drug and 15.1 without: 16.8 months longer.
- 2,100 patients × 16.8 months = about 2,900 years of life.

What this assumes:

- Every eligible patient is counted. Not all of them would have taken the drug. That is why the page says "at stake".
- The median gain in the trial stands in for the average gain.
- The trial result holds for patients outside the trial.

A drug is only counted when a randomised trial reported a median survival for both groups and a patient count could be sourced.

## What is not here yet

- The human cost of the other 279 drugs. Most were never tested for how much longer patients live, so their cost is harder to count. It is not zero.
- Drugs still waiting for a decision today.
- Vaccines, gene therapies and blood products, which a different FDA centre reviews.
- Approvals after December 2025, until the FDA updates its spreadsheet.

## Repository layout

```
data/raw/                  the FDA's files, as downloaded
data/human_cost.json       hand-checked human cost inputs, with sources
data/drugs.json            the output: one record per drug (open data)
scripts/build.py           reads the data, writes drugs.json and the page
scripts/template.html      the page layout, styles and script
docs/index.html            the built dashboard (served as the website)
```

## Build it yourself

You need [uv](https://docs.astral.sh/uv/). Then:

```bash
uv run scripts/build.py
```

This rewrites `data/drugs.json` and `docs/index.html`. The page is one self-contained file; open it in any browser.

To re-download the rejection letters first:

```bash
uv run scripts/build.py --refresh-crl
```

To update the approvals spreadsheet, download it in a browser from the link above and save it over the file in `data/raw`. The FDA site refuses downloads from some servers.

## Contribute

- **Add a drug's human cost:** add an entry to `data/human_cost.json` under the drug's `id` from `data/drugs.json`, with a source link and quote for each number, and rebuild.
- **Correct a number:** open an issue or a pull request with the source.
- Edit `scripts/template.html`, not `docs/index.html`, which is overwritten on every build.

## Licence

The code is under the MIT licence. The FDA's data is a work of the US government and in the public domain. This is not medical advice.
