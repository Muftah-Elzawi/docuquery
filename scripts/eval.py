"""Citation accuracy on the sample documents, measured end-to-end through the HTTP API.

For each question we know which document and page hold the answer. A question counts as
correct when the answer cites (as [n]) at least one source on that document and page.
Retrieval hit@1 (the top source is the right page) is reported separately.

Usage:
    python scripts/make_sample_docs.py
    python scripts/eval.py [--base-url http://localhost:8000] [--samples sample_docs]
"""

import argparse
import re
import uuid
from pathlib import Path

import httpx

ALPENBLICK = "rechnung_alpenblick_2026-0412.pdf"
CHIEMGAU = "rechnung_fehlerhaft_2026-0419.pdf"
POLICY = "reisekostenrichtlinie_inntal.pdf"

# (question, expected document, expected page)
QUESTIONS: list[tuple[str, str, int]] = [
    ("Wie hoch ist die Verpflegungspauschale für volle Kalendertage?", POLICY, 2),
    ("Bis zu welchem Betrag werden Hotelkosten in München erstattet?", POLICY, 1),
    ("Ab welcher Fahrtzeit ist die 1. Klasse bei Bahnfahrten erlaubt?", POLICY, 1),
    ("Innerhalb welcher Frist müssen Reisekosten eingereicht werden?", POLICY, 2),
    ("Wer muss Flugreisen innerhalb Deutschlands genehmigen?", POLICY, 1),
    ("Wie hoch ist der Gesamtbetrag der Rechnung RE-2026-0412?", ALPENBLICK, 1),
    ("Was kostet der Antriebsriemen auf der Rechnung von Alpenblick Maschinenbau?", ALPENBLICK, 1),
    ("Welches Zahlungsziel hat die Rechnung von Alpenblick Maschinenbau?", ALPENBLICK, 1),
    ("Wie hoch ist der Nettobetrag der Rechnung von Chiemgau Elektro?", CHIEMGAU, 1),
    ("What is the invoice date of invoice CE-2026-0419?", CHIEMGAU, 1),
]


def setup_workspace(client: httpx.Client, samples: Path) -> dict:
    email = f"eval-{uuid.uuid4().hex[:8]}@inntal.example"
    r = client.post("/api/auth/register", json={"workspace_name": "Eval Inntal Logistik", "email": email,
                                                "password": "eval-password-123"})
    r.raise_for_status()
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    for name in (ALPENBLICK, CHIEMGAU, POLICY):
        with (samples / name).open("rb") as f:
            doc = client.post("/api/documents", headers=headers, files={"file": (name, f, "application/pdf")})
        doc.raise_for_status()
        if doc.json()["status"] != "ready":
            raise SystemExit(f"Ingestion failed for {name}: {doc.json()['error']}")
    return headers


def cited_sources(answer: str, sources: list[dict]) -> list[dict]:
    numbers = {int(n) for n in re.findall(r"\[(\d+)\]", answer)}
    return [s for s in sources if s["number"] in numbers]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--samples", default="sample_docs", type=Path)
    args = parser.parse_args()

    with httpx.Client(base_url=args.base_url, timeout=300) as client:
        headers = setup_workspace(client, args.samples)
        cited_ok = top1_ok = 0
        print("| # | Question | Expected | Top source | Cited | Correct |")
        print("|---|---|---|---|---|---|")
        for i, (question, filename, page) in enumerate(QUESTIONS, start=1):
            r = client.post("/api/ask", headers=headers, json={"question": question})
            r.raise_for_status()
            body = r.json()
            cited = cited_sources(body["answer"], body["sources"])
            ok = any(s["filename"] == filename and s["page"] == page for s in cited)
            cited_ok += ok
            top = body["sources"][0] if body["sources"] else None
            top1_ok += bool(top) and (top["filename"], top["page"]) == (filename, page)
            top_str = f"{top['filename']} p.{top['page']}" if top else "none"
            cited_str = ", ".join(f"{s['filename']} p.{s['page']}" for s in cited) or "none"
            print(f"| {i} | {question} | {filename} p.{page} | {top_str} | {cited_str} | {'yes' if ok else 'no'} |")

        n = len(QUESTIONS)
        print(f"\nCorrect page cited: {cited_ok}/{n}   Retrieval hit@1: {top1_ok}/{n}")


if __name__ == "__main__":
    main()
