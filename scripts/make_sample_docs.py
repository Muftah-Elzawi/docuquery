"""Generate fictional sample PDFs for demos and tests. All companies and data are invented.

Usage: python scripts/make_sample_docs.py [output_dir]
"""

import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

DOCS: dict[str, list[list[str]]] = {
    "rechnung_alpenblick_2026-0412.pdf": [[
        "Alpenblick Maschinenbau GmbH",
        "Industriestrasse 12, 83022 Rosenheim",
        "",
        "Rechnung",
        "Rechnungsnummer: RE-2026-0412",
        "Rechnungsdatum: 14.09.2026",
        "Kunde: Inntal Logistik AG",
        "",
        "Pos. 1  Wartung Foerderband FB-3        2 x 480,00 EUR     960,00 EUR",
        "Pos. 2  Ersatzteil Antriebsriemen       1 x 240,00 EUR     240,00 EUR",
        "",
        "Nettobetrag: 1.200,00 EUR",
        "MwSt. 19%: 228,00 EUR",
        "Gesamtbetrag: 1.428,00 EUR",
        "",
        "Zahlbar innerhalb von 14 Tagen ohne Abzug.",
    ]],
    "rechnung_fehlerhaft_2026-0419.pdf": [[
        "Chiemgau Elektro KG",
        "Rechnung",
        "Rechnungsnummer: CE-2026-0419",
        "Rechnungsdatum: 02.10.2026",
        "Kunde: Inntal Logistik AG",
        "",
        "Pos. 1  Installation LED-Hallenbeleuchtung   3.000,00 EUR",
        "",
        "Nettobetrag: 3.000,00 EUR",
        "MwSt. 19%: 570,00 EUR",
        "Gesamtbetrag: 3.750,00 EUR",
    ]],
    "reisekostenrichtlinie_inntal.pdf": [
        [
            "Inntal Logistik AG - Reisekostenrichtlinie (gueltig ab 01.01.2026)",
            "",
            "1. Geltungsbereich",
            "Diese Richtlinie gilt fuer alle Dienstreisen von Mitarbeitenden der Inntal Logistik AG.",
            "",
            "2. Verkehrsmittel",
            "Bahnfahrten werden in der 2. Klasse erstattet. Ab einer Fahrtzeit von mehr als",
            "vier Stunden ist die 1. Klasse erlaubt. Flugreisen innerhalb Deutschlands",
            "muessen vorab von der Abteilungsleitung genehmigt werden.",
            "",
            "3. Uebernachtung",
            "Hotelkosten werden bis maximal 130 EUR pro Nacht erstattet, in Muenchen und",
            "Frankfurt bis maximal 160 EUR pro Nacht.",
        ],
        [
            "4. Verpflegung",
            "Fuer Abwesenheiten von mehr als 8 Stunden gilt eine Pauschale von 14 EUR,",
            "fuer volle Kalendertage von 28 EUR.",
            "",
            "5. Abrechnung",
            "Reisekosten muessen spaetestens 30 Tage nach Reiseende ueber das",
            "Reisekostenportal eingereicht werden. Belege sind digital beizufuegen.",
        ],
    ],
}


def write_pdf(path: Path, pages: list[list[str]]) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    for lines in pages:
        y = 800
        for line in lines:
            c.drawString(60, y, line)
            y -= 18
        c.showPage()
    c.save()


def main(out_dir: str = "sample_docs") -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, pages in DOCS.items():
        write_pdf(out / name, pages)
        print(f"wrote {out / name}")


if __name__ == "__main__":
    main(*sys.argv[1:])
