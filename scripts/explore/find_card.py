from selectolax.lexbor import LexborHTMLParser

with open("step1_dump.html", encoding="utf-8") as f:
    html = f.read()

tree = LexborHTMLParser(html)
h2 = tree.css_first("h2.job-internship-name")

node = h2
for depth in range(9):
    node = node.parent
    if node is None:
        break
    text = node.text(separator=" | ", strip=True)
    has_stipend = "₹" in text
    print(f"--- depth {depth} | tag={node.tag} class={node.attributes.get('class', '')!r} "
          f"| len={len(text)} | stipend={has_stipend}")
    print("    ", text[:300].replace("\n", " "))
