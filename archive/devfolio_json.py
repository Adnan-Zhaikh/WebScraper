import json
from selectolax.lexbor import LexborHTMLParser

with open("devfolio_dump.html", encoding="utf-8") as f:
    html = f.read()

tree = LexborHTMLParser(html)
script = tree.css_first("script#__NEXT_DATA__")

if script is None:
    print("no __NEXT_DATA__ found — dumping script tags instead")
    for s in tree.css("script"):
        print("  id=", s.attributes.get("id"), "type=", s.attributes.get("type"),
              "len=", len(s.text() or ""))
else:
    data = json.loads(script.text())
    print("top-level keys:", list(data.keys()))
    print("props keys:", list(data.get("props", {}).keys()))

    page_props = data.get("props", {}).get("pageProps", {})
    print("\npageProps keys:", list(page_props.keys()))

    # find the list of hackathons wherever it lives
    def find_lists(obj, path="", depth=0):
        if depth > 5:
            return
        if isinstance(obj, dict):
            for k, v in obj.items():
                find_lists(v, f"{path}.{k}", depth + 1)
        elif isinstance(obj, list) and obj and isinstance(obj[0], dict):
            print(f"  list at {path}: {len(obj)} items, keys={list(obj[0].keys())[:12]}")

    print("\ncandidate lists:")
    find_lists(page_props)
