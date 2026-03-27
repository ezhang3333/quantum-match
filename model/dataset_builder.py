import json
import os
import time

from .settings import PROFILES_PATH, RAW_IMAGES_DIR
from .web_scraper import scrape_perimeter_people, download_image

RATE_LIMIT_SECONDS = 0.5


def build_dataset(target_count: int = 100) -> None:
    print("Scraping Perimeter Institute people page")
    profiles_data = scrape_perimeter_people(target_count)

    profiles = {}
    failed = []

    for person_id, person in profiles_data.items():
        name = person["name"]

        os.makedirs(RAW_IMAGES_DIR, exist_ok=True)
        img_dest = os.path.join(RAW_IMAGES_DIR, f"{person_id}.jpg")

        img_ok = False
        if person["img_url"]:
            img_ok = download_image(person["img_url"], img_dest)
            if not img_ok:
                failed.append(person)
        else:
                failed.append(person)

        time.sleep(RATE_LIMIT_SECONDS)

        profiles[person_id] = {
            "name": name,
            "profile_url": person["profile_url"],
            "role": person["role"],
            "position": person["position"],
            "secondary_position": person["secondary_position"],
            "research_areas": person["research_areas"],
            "image_path": img_dest if img_ok else "",
        }

    os.makedirs(os.path.dirname(PROFILES_PATH), exist_ok=True)
    with open(PROFILES_PATH, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2, ensure_ascii=False)
    
    if failed:
         failed_people_str = "".join(failed)
         print(f"\nPeople who failed: {failed_people_str}")


if __name__ == "__main__":
    build_dataset()
