import httpx

URL = "https://internshala.com/internships/location-mumbai,work_from_home-true"

def main():
    with httpx.Client(
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
            "Accept-Language": "en-IN,en;q=0.9",
        },
        follow_redirects=True,
        timeout=20,
    ) as client:
        resp = client.get(URL)
        print("status:", resp.status_code)
        print("bytes:", len(resp.text))
        with open("step1_dump.html", "w", encoding="utf-8") as f:
            f.write(resp.text)
        print(resp.text[:1200])

if __name__ == "__main__":
    main()
