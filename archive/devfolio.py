import httpx

URL = "https://devfolio.co/hackathons"

with httpx.Client(
    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"},
    follow_redirects=True,
    timeout=25,
) as client:
    resp = client.get(URL)
    print("status:", resp.status_code)
    print("bytes:", len(resp.text))
    print("final url:", resp.url)

    with open("devfolio_dump.html", "w", encoding="utf-8") as f:
        f.write(resp.text)

    text = resp.text
    print("has 'hackathon' in html:", text.lower().count("hackathon"))
    print("looks like a JS shell:", len(text) < 5000)
    print(text[:800])
