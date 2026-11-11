"""Record every JSON response a page loads, so we can find the schedule endpoint.
 
Usage:
    python discover.py https://app.fitssey.com/czulosfera/frontoffice --out captures/czulosfera
 
A visible browser window opens. Click through the schedule (next week, filters...),
then press Enter in the terminal. Each JSON response is saved to its own file and
an index.json lists URL, method and status. Request headers are NOT saved, so no
tokens end up on disk. Only browse anonymously (do not log in).
"""
from __future__ import annotations
 
import argparse
import json
import re
from pathlib import Path
 
from playwright.sync_api import sync_playwright
 
 
def slugify(url: str, max_len: int = 60) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", url.split("://", 1)[-1])[:max_len].strip("_")
 
 
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--out", default="captures/default")
    args = parser.parse_args()
 
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    index: list[dict] = []
 
    def on_response(response) -> None:
        if "json" not in response.headers.get("content-type", ""):
            return
        try:
            body = response.json()
        except Exception:
            return  # not valid JSON or body unavailable
        file_name = f"{len(index) + 1:03d}_{slugify(response.url)}.json"
        (out_dir / file_name).write_text(
            json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        index.append(
            {
                "file": file_name,
                "method": response.request.method,
                "url": response.url,
                "status": response.status,
                "post_data": response.request.post_data,
            }
        )
        print(f"saved {file_name}  <- {response.request.method} {response.url}")
 
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        page = browser.new_page()
        page.on("response", on_response)
        page.goto(args.url, wait_until="networkidle")
        input("Click through the schedule, then press Enter here to finish... ")
        browser.close()
 
    (out_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Done. {len(index)} JSON responses saved in {out_dir}/")
 
 
if __name__ == "__main__":
    main()