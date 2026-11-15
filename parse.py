from selectolax.lexbor import LexborHTMLParser

with open("step1_dump.html", encoding="utf-8") as f:
    html = f.read()

tree = LexborHTMLParser(html)

candidates = {}
for a in tree.css("a[href*='/internship/detail/']"):
    parent = a.parent
    if parent is None:
        continue
    key = (parent.tag, parent.attributes.get("class", ""))
    candidates[key] = candidates.get(key, 0) + 1

print("Candidate containers (tag, class) -> link count:")
for key, count in sorted(candidates.items(), key=lambda kv: -kv[1])[:10]:
    print(f"  {key}  ->  {count}")

links = tree.css("a[href*='/internship/detail/']")
print(f"\nTotal detail links: {len(links)}")
for a in links[:5]:
    print(" ", a.text(strip=True)[:60], "|", a.attributes.get("href"))
