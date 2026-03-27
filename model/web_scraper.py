import math
import re

from scrapling.fetchers import StealthySession
from .settings import BASE_URL, PERIMETER_PEOPLE_URL
from bs4 import BeautifulSoup


def scrape_perimeter_people(target_count: int = 100) -> dict:
    """Scrape and parse Perimeter Institute people cards"""
    pages_needed = math.ceil(target_count / 12)
    seen = set()
    people = {}

    with StealthySession(headless=True, solve_cloudflare=True) as session:
        for page_num in range(pages_needed):
            url = PERIMETER_PEOPLE_URL if page_num == 0 else f"{PERIMETER_PEOPLE_URL}?page={page_num}"

            response = session.fetch(url)
            html = response.body.decode("utf-8", errors="replace")

            soup = BeautifulSoup(html, "html.parser")
            cards = soup.select("div.card[about]")

            if not cards:
                raise ValueError(f"No cards found on page {page_num}")

            for card in cards:
                about = card.get("about", "")
                if not about or about in seen:
                    continue
                seen.add(about)

                name_tag = card.select_one("h3.card-heading a span")
                name = name_tag.get_text(strip=True) if name_tag else ""
                if not name:
                    continue

                img_tag = card.select_one("div.card-media img")
                img_src = img_tag.get("src", "") if img_tag else ""
                if img_src and img_src.startswith("/"):
                    img_src = BASE_URL + img_src

                role_tag = card.select_one("p.field--field-role")
                role = role_tag.get_text(" ", strip=True) if role_tag else ""

                position_tag = card.select_one("div.field--field-position")
                position = position_tag.get_text(strip=True) if position_tag else ""

                secondary_position_tag = card.select_one("div.field--field-secondary-position")
                secondary_position = secondary_position_tag.get_text(strip=True) if secondary_position_tag else ""

                research_area_tags = card.select("div.field--field-people-research-area div")
                research_areas = [t.get_text(strip=True) for t in research_area_tags]

                people[name] = {
                    "name": name,
                    "profile_url": BASE_URL + about,
                    "img_url": img_src,
                    "role": role,
                    "position": position,
                    "secondary_position": secondary_position,
                    "research_areas": research_areas,
                }

            if len(people) >= target_count:
                break

    return people


def download_image(url: str, dest_path: str) -> bool:
    """Download an image URL to dest_path using a stealthy session"""
    try:
        with StealthySession(headless=True, solve_cloudflare=True) as session:
            response = session.fetch(url)
            if not response or not response.body:
                return False
            with open(dest_path, "wb") as f:
                f.write(response.body)
        return True
    except Exception as e:
        raise Exception(f"Caught error: {e}")


def scrape_quantum_people(url: str) -> str:
    """Web scrapes a URL and returns the body html"""
    if not url:
        return
    
    with StealthySession(headless=True, solve_cloudflare=True) as session:
        page = session.fetch(url)
        html = page.body.decode("utf-8", errors="replace")

    return html