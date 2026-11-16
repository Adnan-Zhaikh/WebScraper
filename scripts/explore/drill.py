# step6c_drill.py
import json
from selectolax.lexbor import LexborHTMLParser

with open("devfolio_dump.html", encoding="utf-8") as f:
    html = f.read()

data = json.loads(LexborHTMLParser(html).css_first("script#__NEXT_DATA__").text())
q = data["props"]["pageProps"]["dehydratedState"]["queries"][0]

print("queryKey:", q.get("queryKey"))
print("queryHash:", q.get("queryHash"))
print("state keys:", list(q.get("state", {}).keys()))

state_data = q["state"].get("data")
print("\ndata type:", type(state_data).__name__)

if isinstance(state_data, dict):
    print("data keys:", list(state_data.keys()))
    for k, v in state_data.items():
        if isinstance(v, list):
            print(f"  {k}: list of {len(v)}")
            if v and isinstance(v[0], dict):
                print("    item keys:", list(v[0].keys()))
                print(json.dumps(v[0], indent=2, ensure_ascii=False)[:1200])
elif isinstance(state_data, list):
    print("list of", len(state_data))
    if state_data:
        print("item keys:", list(state_data[0].keys()))
        print(json.dumps(state_data[0], indent=2, ensure_ascii=False)[:1200])
