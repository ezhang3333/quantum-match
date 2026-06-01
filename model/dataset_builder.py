import argparse
import json
import os
import time
import unicodedata

from .settings import PROFILE_INFO_PATH, PROFILES_PATH, RAW_IMAGES_DIR
from .web_scraper import (
    download_image,
    scrape_iquist_people,
    scrape_perimeter_people,
    scrape_perimeter_profile_info,
    scrape_quantum_ctos,
)

RATE_LIMIT_SECONDS = 0.5


def _load_profiles(path: str) -> dict:
    if not os.path.exists(path):
        return {}

    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _ascii_safe_filename(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_name = ascii_name.replace("/", " ").replace("\\", " ")
    return " ".join(ascii_name.split()) or "profile"


def build_dataset(target_count: int = 100) -> None:
    print("Scraping Perimeter Institute people page")
    profiles_data = scrape_perimeter_people(target_count)

    profiles = {}
    profile_info = {}
    failed = []
    failed_names = []
    duplicate_names = []

    os.makedirs(RAW_IMAGES_DIR, exist_ok=True)

    for person_id, person in profiles_data.items():
        name = person["name"]
        img_dest = os.path.join(RAW_IMAGES_DIR, f"{person_id}.jpg")

        img_ok = False
        if person["img_url"]:
            img_ok = download_image(person["img_url"], img_dest)
            if not img_ok:
                failed.append(person)
                failed_names.append(name)
        else:
            failed.append(person)
            failed_names.append(name)

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
        profile_details = scrape_perimeter_profile_info(person["profile_url"])
        profile_info[person_id] = {
            "name": name,
            "profile_url": person["profile_url"],
            "teaching_affiliations": profile_details["teaching_affiliations"],
            "research_interests": profile_details["research_interests"],
            "awards": profile_details["awards"],
        }

        time.sleep(RATE_LIMIT_SECONDS)

    print("Scraping iQuIST members page")
    iquist_profiles, iquist_duplicates = scrape_iquist_people(target_count=50)
    duplicate_names.extend(iquist_duplicates)

    for person_id, person in iquist_profiles.items():
        if person_id in profiles:
            duplicate_names.append(person_id)
            continue

        img_dest = os.path.join(RAW_IMAGES_DIR, f"{person_id}.jpg")
        img_ok = False
        if person["img_url"]:
            img_ok = download_image(person["img_url"], img_dest)
            if not img_ok:
                failed.append(person)
                failed_names.append(person_id)
        else:
            failed.append(person)
            failed_names.append(person_id)

        time.sleep(RATE_LIMIT_SECONDS)

        profiles[person_id] = {
            "name": person["name"],
            "profile_url": person["profile_url"],
            "role": person["role"],
            "position": person["position"],
            "secondary_position": person["secondary_position"],
            "research_areas": person["research_areas"],
            "summary": person["summary"],
            "category": person["category"],
            "image_path": img_dest if img_ok else "",
        }

    os.makedirs(os.path.dirname(PROFILES_PATH), exist_ok=True)
    with open(PROFILES_PATH, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2, ensure_ascii=False)

    with open(PROFILE_INFO_PATH, "w", encoding="utf-8") as f:
        json.dump(profile_info, f, indent=2, ensure_ascii=False)

    if failed:
        failed_people_str = ", ".join(failed_names)
        print(f"\nPeople who failed image download: {failed_people_str}")

    if duplicate_names:
        duplicate_people_str = ", ".join(sorted(set(duplicate_names)))
        print(f"\nSkipped duplicate names: {duplicate_people_str}")


def merge_quantum_ctos() -> None:
    print("Scraping Quantum Insider CTO article")
    cto_profiles = scrape_quantum_ctos()
    profiles = _load_profiles(PROFILES_PATH)

    failed_names = []
    duplicate_names = []
    added_names = []

    os.makedirs(RAW_IMAGES_DIR, exist_ok=True)

    for person_id, person in cto_profiles.items():
        if person_id in profiles:
            duplicate_names.append(person_id)
            continue

        img_dest = os.path.join(RAW_IMAGES_DIR, f"{_ascii_safe_filename(person_id)}.jpg")
        img_ok = False
        if person["img_url"]:
            img_ok = download_image(person["img_url"], img_dest)
            if not img_ok:
                failed_names.append(person_id)
        else:
            failed_names.append(person_id)

        profiles[person_id] = {
            "name": person["name"],
            "profile_url": person["profile_url"],
            "role": person["role"],
            "position": person["position"],
            "secondary_position": person["secondary_position"],
            "research_areas": person["research_areas"],
            "summary": person["summary"],
            "category": person["category"],
            "image_path": img_dest if img_ok else "",
        }
        added_names.append(person_id)
        time.sleep(RATE_LIMIT_SECONDS)

    with open(PROFILES_PATH, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2, ensure_ascii=False)

    print(f"\nAdded CTO profiles: {len(added_names)}")
    if failed_names:
        print(f"People who failed image download: {', '.join(failed_names)}")
    if duplicate_names:
        print(f"Skipped duplicate names: {', '.join(sorted(duplicate_names))}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--merge-quantum-ctos",
        action="store_true",
        help="Merge Quantum Insider CTO profiles into the existing profiles dataset.",
    )
    args = parser.parse_args()

    if args.merge_quantum_ctos:
        merge_quantum_ctos()
    else:
        build_dataset()
