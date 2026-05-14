"""Generate the CORA hero image (bloom) via Recraft API and save to docs/assets/."""
from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

TOKEN = os.environ["RECRAFT_API_TOKEN"]
OUT_DIR = ROOT / "docs" / "assets"
OUT_DIR.mkdir(parents=True, exist_ok=True)

API_URL = "https://external.api.recraft.ai/v1/images/generations"
SIZE = "1820x1024"

PROMPTS: dict[str, tuple[str, str]] = {
    "hero-bloom": (
        "realistic_image",
        "A single bioluminescent flower in macro photograph composition, positioned in the "
        "lower-right third of the frame, petals glowing with internal teal #0A7E8C and cyan "
        "#2DD4BF light, growing from cracked dark alien soil with faint mineral glints, deep "
        "black negative space filling the upper-left two-thirds of the frame, shallow depth "
        "of field with the flower in sharp focus, slightly uncanny botanical quality "
        "reminiscent of Zdzislaw Beksinski and macro nature photography, dewdrops on petals "
        "catching the glow, no text, no logos, no other plants",
    ),
}


def generate(name: str, style: str, prompt: str) -> tuple[str, Path | str]:
    try:
        with httpx.Client(timeout=120.0) as client:
            r = client.post(
                API_URL,
                headers={"Authorization": f"Bearer {TOKEN}"},
                json={
                    "prompt": prompt,
                    "style": style,
                    "size": SIZE,
                    "model": "recraftv3",
                    "n": 1,
                },
            )
            r.raise_for_status()
            url = r.json()["data"][0]["url"]
            img = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            img.raise_for_status()
        out = OUT_DIR / f"{name}.png"
        out.write_bytes(img.content)
        return name, out
    except Exception as e:
        return name, f"ERROR: {e!r}"


def main() -> int:
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {
            pool.submit(generate, name, style, prompt): name
            for name, (style, prompt) in PROMPTS.items()
        }
        results = []
        for fut in as_completed(futures):
            name, result = fut.result()
            print(f"[{name}] {result}")
            results.append((name, result))

    failures = [r for r in results if isinstance(r[1], str)]
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
