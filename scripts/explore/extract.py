import json
from selectolax.lexbor import LexborHTMLParser

with open("step1_dump.html", encoding="utf-8") as f:
    html = f.read()

tree = LexborHTMLParser(html)
rows = []

for h2 in tree.css("h2.job-internship-name"):
    a = h2.css_first("a")
    if a is None:
        continue

    # walk up to the card container
    card = h2
    for _ in range(4):
        if card.parent is None:
            break
        card = card.parent
        if card.css_first(".company-name") or card.css_first(".location_link"):
            break

    def txt(sel):
        el = card.css_first(sel)
        return el.text(strip=True) if el else None

    rows.append({
        "title": a.text(strip=True),
        "url": "https://internshala.com" + a.attributes.get("href", ""),
        "company": txt(".company-name") or txt(".company_name"),
        "location": txt(".location_link") or txt(".locations"),
        "stipend": txt(".stipend"),
        "duration": txt(".ic-16-calendar") and card.css_first(".ic-16-calendar").parent.text(strip=True),
        "card_text": card.text(separator=" | ", strip=True)[:400],
    })

print(f"parsed {len(rows)} rows\n")
for r in rows[:3]:
    print(json.dumps(r, indent=2, ensure_ascii=False))
