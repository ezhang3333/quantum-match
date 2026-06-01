import math
import re
from urllib.parse import urljoin

from scrapling.fetchers import StealthySession
from bs4 import BeautifulSoup

from .settings import (
    BASE_URL,
    IQUIST_BASE_URL,
    IQUIST_PEOPLE_URL,
    PERIMETER_PEOPLE_URL,
    QUANTUM_INSIDER_CTO_URL,
)


WHITESPACE_RE = re.compile(r"\s+")
BODIES_SELECTOR = ".accordion-item-item-body, .accordion-item-body"
BACKGROUND_URL_RE = re.compile(r'url\(["\']?(.*?)["\']?\)')
IQUIST_FALLBACK_SUMMARY = (
    "Profile details for this researcher are not yet available in the current dataset."
)
IQUIST_STOP_SECTIONS = {
    "selected articles in journals",
    "pending articles",
    "recent courses taught",
    "load more news",
}
IQUIST_SKIP_SECTIONS = {
    "education",
    "post-doctoral research opportunities",
    "graduate research opportunities",
}
IQUIST_SUMMARY_SECTIONS = {
    "biography",
    "research interests",
}
IQUIST_TITLE_KEYWORDS = (
    "professor",
    "assistant professor",
    "associate professor",
    "director",
    "chair",
    "scientist",
    "lecturer",
)
IQUIST_SUMMARY_SKIP_EXACT = {
    "publications",
    "research areas/expertise:",
    "research areas/expertise",
    "research expertise:",
    "research expertise",
}
QUANTUM_CTO_HEADING_RE = re.compile(r"^\s*(\d+)\.\s*(.+?):\s*CTO at\s+(.+?)\s*$")


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


def _normalize_text(text: str) -> str:
    """Collapse repeated whitespace into readable single-space text."""
    return WHITESPACE_RE.sub(" ", text).strip()


def _decode_html(html: bytes | str) -> str:
    """Decode HTML content into a normalized text string."""
    if isinstance(html, bytes):
        return html.decode("utf-8", errors="replace")
    return html


def _extract_background_image_url(style_value: str, base_url: str) -> str:
    """Extract a background-image URL from an inline style value."""
    if not style_value:
        return ""

    match = BACKGROUND_URL_RE.search(style_value)
    if not match:
        return ""

    return urljoin(base_url, match.group(1))


def _extract_image_url(soup: BeautifulSoup, base_url: str) -> str:
    """Best-effort image extraction from figure img tags or hero backgrounds."""
    figure_img = soup.select_one("figure img")
    if figure_img and figure_img.get("src"):
        return urljoin(base_url, figure_img["src"])

    figure_link = soup.select_one('figure a[href*="viewphoto"], figure a[href$=".jpg"], figure a[href$=".png"]')
    if figure_link and figure_link.get("href"):
        return urljoin(base_url, figure_link["href"])

    hero = soup.select_one("#hero")
    if hero:
        hero_img = _extract_background_image_url(hero.get("style", ""), base_url)
        if hero_img:
            return hero_img

    photo = soup.select_one("div.photo")
    if photo:
        return _extract_background_image_url(photo.get("style", ""), base_url)

    return ""


def _extract_quantum_cto_summary(entry_heading) -> tuple[str, str, str]:
    """Extract image URL, person link, and concatenated summary for a CTO entry."""
    image_url = ""
    profile_url = ""
    paragraphs = []

    node = entry_heading.find_next_sibling()
    while node is not None:
        if getattr(node, "name", None) == "h3" and node.get("class") and "graf--h3" in node.get("class"):
            break

        if getattr(node, "name", None) == "figure" and not image_url:
            image_tag = node.find("img")
            if image_tag and image_tag.get("src"):
                image_url = _normalize_text(image_tag["src"])

        if getattr(node, "name", None) == "p":
            text = _normalize_text(node.get_text(" ", strip=True))
            if text and text != "nbsp;":
                paragraphs.append(text)

            if not profile_url:
                link_tag = node.find("a", href=True)
                if link_tag:
                    profile_url = _normalize_text(link_tag["href"])

        node = node.find_next_sibling()

    return image_url, profile_url, "\n\n".join(paragraphs)


def scrape_quantum_ctos(article_url: str = QUANTUM_INSIDER_CTO_URL) -> dict:
    """Scrape Quantum Insider CTO profiles from the article page."""
    with StealthySession(headless=True, solve_cloudflare=True) as session:
        response = session.fetch(article_url)
        html = _decode_html(response.body)

    soup = BeautifulSoup(html, "html.parser")
    people = {}

    for heading in soup.select("h3.graf.graf--h3"):
        heading_text = _normalize_text(heading.get_text(" ", strip=True))
        match = QUANTUM_CTO_HEADING_RE.match(heading_text)
        if not match:
            continue

        _, name, company = match.groups()
        image_url, profile_url, summary = _extract_quantum_cto_summary(heading)

        people[name] = {
            "name": name,
            "profile_url": profile_url or article_url,
            "img_url": image_url,
            "role": "CTO",
            "position": f"CTO at {company}",
            "secondary_position": "",
            "research_areas": [],
            "summary": summary,
            "category": "engineers",
        }

    return people


def _extract_iquist_member_cards(soup: BeautifulSoup, target_count: int) -> list:
    """Return the first target_count member cards from the Members section only."""
    members_heading = None
    for heading in soup.find_all("h2"):
        if _normalize_text(heading.get_text(" ", strip=True)).lower() == "members":
            members_heading = heading
            break

    if members_heading is None:
        return []

    cards = []
    for sibling in members_heading.find_next_siblings():
        if sibling.name == "h2" and _normalize_text(sibling.get_text(" ", strip=True)).lower() == "affiliates":
            break

        cards.extend(sibling.select("div.item.person"))
        if len(cards) >= target_count:
            return cards[:target_count]

    return cards[:target_count]


def _extract_iquist_research_areas_from_detail(column) -> list[str]:
    """Extract Research Areas/Expertise bullets from an iQuIST detail page."""
    label = column.find(string=re.compile(r"Research Areas/Expertise", re.IGNORECASE))
    if label is None:
        return []

    label_parent = label.parent
    list_tag = label_parent.find_next("ul") if label_parent else None
    if list_tag is None:
        return []

    areas = [_normalize_text(item.get_text(" ", strip=True)) for item in list_tag.select("li")]
    return [area for area in areas if area]


def _extract_iquist_secondary_position(column, role_tag, address_div) -> str:
    """Extract a second short title-like line between the role and address blocks."""
    if role_tag is None or address_div is None:
        return ""

    seen_role = False
    for child in column.children:
        if not getattr(child, "name", None):
            continue

        if child is role_tag:
            seen_role = True
            continue
        if child is address_div:
            break
        if not seen_role:
            continue

        if child.name not in {"p", "div"}:
            continue

        text = _normalize_text(child.get_text(" ", strip=True))
        if not text:
            continue
        if text.lower().startswith(("phone:", "e-mail:", "email:")):
            continue
        if len(text.split()) > 8:
            continue

        return text

    return ""


def _extract_iquist_position_without_address(column, role_text: str) -> tuple[str, str]:
    """Fallback extraction when the page has no structured address block."""
    position = ""
    secondary_position = ""
    seen_role = False

    for child in column.children:
        if not getattr(child, "name", None):
            continue

        text = _normalize_text(child.get_text(" ", strip=True))
        if not text:
            continue
        if text == role_text:
            seen_role = True
            continue
        if not seen_role:
            continue
        if text.lower().startswith(("phone:", "e-mail:", "email:", "education", "biography")):
            break

        if not position and len(text.split()) <= 8:
            position = text
            continue
        if not secondary_position and len(text.split()) <= 8:
            secondary_position = text
            break
        break

    return position, secondary_position


def _extract_iquist_text_items(column, name: str) -> list[str]:
    """Flatten meaningful text from the main iQuIST content column."""
    items = []
    for raw_text in column.stripped_strings:
        text = _normalize_text(raw_text)
        if not text:
            continue
        if items and items[-1] == text:
            continue
        items.append(text)

    while items and items[0] == name:
        items = items[1:]

    return items


def _extract_iquist_research_areas_from_text_items(text_items: list[str]) -> list[str]:
    """Fallback text-based extraction of Research Areas/Expertise bullets."""
    areas = []
    collecting = False

    for item in text_items:
        lower_item = item.lower().rstrip(":")
        if lower_item == "research areas/expertise":
            collecting = True
            continue
        if not collecting:
            continue
        if lower_item in {"publications", "biography", "education"}:
            break
        if lower_item.startswith(("http", "phone", "e-mail", "email")):
            break
        areas.append(item)

    return areas


def _extract_iquist_position_fields_from_text_items(text_items: list[str]) -> tuple[str, str, str]:
    """Fallback text-based extraction of role, position, and secondary position."""
    preamble = []
    for item in text_items:
        lower_item = item.lower().rstrip(":")
        if lower_item in {
            "education",
            "biography",
            "research areas/expertise",
            "research interests",
            "post-doctoral research opportunities",
            "graduate research opportunities",
            "publications",
        }:
            break
        if lower_item.startswith(("phone", "e-mail", "email")):
            break
        preamble.append(item)
        if len(preamble) >= 6:
            break

    if not preamble:
        return "", "", ""

    role = preamble[0]
    position = ""
    secondary_position = ""

    for item in preamble[1:]:
        lower_item = item.lower()
        if any(keyword in lower_item for keyword in IQUIST_TITLE_KEYWORDS):
            position = item
            break

    if position:
        for item in preamble[1:]:
            if item == position:
                break
            secondary_position = item
            break

    return role, position, secondary_position


def _collect_iquist_section(text_items: list[str], start_label: str, stop_labels: set[str]) -> list[str]:
    """Collect text items after a section label until another major section begins."""
    collecting = False
    collected = []

    for item in text_items:
        lower_item = item.lower().rstrip(":")
        if lower_item == start_label:
            collecting = True
            continue
        if not collecting:
            continue
        if lower_item in stop_labels:
            break
        collected.append(item)

    return collected


def _extract_iquist_summary_from_text_items(text_items: list[str]) -> str:
    """Fallback text-based summary extraction from Biography and Research Interests sections."""
    biography = _collect_iquist_section(
        text_items,
        "biography",
        {
            "post-doctoral research opportunities",
            "graduate research opportunities",
            "research interests",
            *IQUIST_STOP_SECTIONS,
        },
    )
    research_interests = _collect_iquist_section(
        text_items,
        "research interests",
        set(IQUIST_STOP_SECTIONS),
    )

    summary_parts = biography + research_interests
    if not summary_parts:
        return IQUIST_FALLBACK_SUMMARY

    return _normalize_text(" ".join(summary_parts))


def _extract_iquist_summary(column) -> str:
    """Broad extraction of descriptive profile prose from iQuIST paragraph content."""
    summary_parts = []

    role_tag = column.select_one("p.m-0.font-weight-bold.hide-empty")
    role_text = _normalize_text(role_tag.get_text(" ", strip=True)) if role_tag else ""
    position_text = ""
    address_div = column.select_one("div.address")
    if address_div is not None:
        strong_tag = address_div.find("strong")
        if strong_tag:
            position_text = _normalize_text(strong_tag.get_text(" ", strip=True))

    for paragraph in column.select("p"):
        text = _normalize_text(paragraph.get_text(" ", strip=True))
        if not text:
            continue

        lower_text = text.lower().rstrip(":")
        if text == role_text or text == position_text:
            continue
        if lower_text in IQUIST_SUMMARY_SKIP_EXACT:
            continue
        if any(stop_label in lower_text for stop_label in IQUIST_STOP_SECTIONS):
            break
        if "research group" in lower_text or "group website" in lower_text:
            continue
        if lower_text.startswith(("phone:", "e-mail:", "email:")):
            continue
        if len(text.split()) <= 6 and any(keyword in lower_text for keyword in IQUIST_TITLE_KEYWORDS):
            continue
        if "@" in text and len(text.split()) <= 6:
            continue
        if "publications" == lower_text or lower_text.endswith(" publications"):
            continue
        if len(text.split()) <= 2 and not paragraph.find("strong"):
            continue

        # Skip short address-only blocks already represented in structured fields.
        if (
            len(text.split()) <= 16
            and any(char.isdigit() for char in text)
            and "." not in text
            and lower_text.count(",") <= 1
        ):
            continue

        summary_parts.append(text)

    if not summary_parts:
        return IQUIST_FALLBACK_SUMMARY

    return _normalize_text(" ".join(summary_parts))


def _find_iquist_content_column(soup: BeautifulSoup):
    """Locate the main iQuIST person-content column."""
    column = soup.select_one("section.tile.w110.white-box div.lower.article div.row div.col")
    if column is not None:
        return column

    heading = soup.find("h1")
    if heading:
        column = heading.find_parent("div", class_=lambda classes: classes and "col" in classes)
        if column is not None:
            return column

    column = soup.select_one("section.tile.w10.white-box div.row div.col.maxwidth1140")
    if column is not None:
        return column

    column = soup.select_one("section.tile.w10.white-box div.row div.col")
    if column is not None:
        return column

    return soup.select_one("main div.col")


def _parse_iquist_profile_page(profile_url: str, fallback_research_areas: list[str]) -> dict:
    """Extract role, position, headshot, summary, and detail research areas from an iQuIST profile."""
    with StealthySession(headless=True, solve_cloudflare=True) as session:
        response = session.fetch(profile_url)
        html = response.body.decode("utf-8", errors="replace")

    soup = BeautifulSoup(html, "html.parser")
    column = _find_iquist_content_column(soup)

    role = ""
    position = ""
    secondary_position = ""
    detail_research_areas = []
    summary = IQUIST_FALLBACK_SUMMARY

    name_tag = column.find("h2") if column is not None else None
    if name_tag is None:
        name_tag = soup.find("h1")
    if name_tag is None:
        name_tag = soup.select_one("section.tile.w10.white-box h2")
    name = _normalize_text(name_tag.get_text(" ", strip=True)) if name_tag else ""

    if column is not None:
        text_items = _extract_iquist_text_items(column, name)
        role_tag = column.select_one("p.m-0.font-weight-bold.hide-empty")
        role = _normalize_text(role_tag.get_text(" ", strip=True)) if role_tag else ""

        address_div = column.select_one("div.address")
        if address_div is not None:
            position_tag = address_div.find("strong")
            if position_tag:
                position = _normalize_text(position_tag.get_text(" ", strip=True))
            secondary_position = _extract_iquist_secondary_position(column, role_tag, address_div)
        else:
            position, secondary_position = _extract_iquist_position_without_address(column, role)

        detail_research_areas = _extract_iquist_research_areas_from_detail(column)
        summary = _extract_iquist_summary(column)
        fallback_role, fallback_position, fallback_secondary = (
            _extract_iquist_position_fields_from_text_items(text_items)
        )
        role = role or fallback_role
        position = position or fallback_position
        secondary_position = secondary_position or fallback_secondary
        detail_research_areas = (
            detail_research_areas or _extract_iquist_research_areas_from_text_items(text_items)
        )
        if summary == IQUIST_FALLBACK_SUMMARY:
            summary = _extract_iquist_summary_from_text_items(text_items)

    return {
        "name": name,
        "role": role,
        "position": position,
        "secondary_position": secondary_position,
        "research_areas": detail_research_areas or fallback_research_areas,
        "img_url": _extract_image_url(soup, IQUIST_BASE_URL),
        "summary": summary,
    }


def scrape_iquist_people(target_count: int = 50) -> tuple[dict, list[str]]:
    """Scrape the first target_count iQuIST Members and enrich them from detail pages."""
    duplicates = []

    with StealthySession(headless=True, solve_cloudflare=True) as session:
        response = session.fetch(IQUIST_PEOPLE_URL)
        html = response.body.decode("utf-8", errors="replace")

    soup = BeautifulSoup(html, "html.parser")
    cards = _extract_iquist_member_cards(soup, target_count)
    if not cards:
        raise ValueError("No iQuIST member cards found")

    people = {}
    for card in cards:
        link = card.select_one("div.name a")
        if link is None:
            continue

        name = _normalize_text(link.get_text(" ", strip=True))
        if not name:
            continue
        if name in people:
            duplicates.append(name)
            continue

        profile_url = urljoin(IQUIST_BASE_URL, link.get("href", ""))
        role_tags = card.select("div.dept li")
        research_area_tags = card.select("div.area li")
        list_research_areas = [
            _normalize_text(tag.get_text(" ", strip=True))
            for tag in research_area_tags
            if _normalize_text(tag.get_text(" ", strip=True))
        ]
        photo_url = _extract_background_image_url(
            card.select_one("div.photo").get("style", "") if card.select_one("div.photo") else "",
            IQUIST_BASE_URL,
        )

        detail_data = _parse_iquist_profile_page(profile_url, list_research_areas)
        role = detail_data["role"]
        if not role and role_tags:
            role = _normalize_text(role_tags[0].get_text(" ", strip=True))

        people[name] = {
            "name": detail_data["name"] or name,
            "profile_url": profile_url,
            "img_url": detail_data["img_url"] or photo_url,
            "role": role,
            "position": detail_data["position"],
            "secondary_position": detail_data["secondary_position"],
            "research_areas": detail_data["research_areas"],
            "summary": detail_data["summary"],
            "category": "engineers",
        }

    return people, duplicates


def _parse_awards(accordion_item) -> list[str]:
    """Extract award entries while preserving list structure when present."""
    body = accordion_item.select_one(BODIES_SELECTOR)
    if body is None:
        return []

    list_items = [
        _normalize_text(item.get_text(" ", strip=True))
        for item in body.select("li")
    ]
    list_items = [item for item in list_items if item]
    if list_items:
        return list_items

    body_text = _normalize_text(body.get_text(" ", strip=True))
    return [body_text] if body_text else []


def scrape_perimeter_profile_info(profile_url: str) -> dict:
    """Scrape teaching affiliations, research interests, and awards from a profile page."""
    empty_profile = {
        "teaching_affiliations": "",
        "research_interests": "",
        "awards": [],
    }
    if not profile_url:
        return empty_profile

    with StealthySession(headless=True, solve_cloudflare=True) as session:
        response = session.fetch(profile_url)
        html = response.body.decode("utf-8", errors="replace")

    soup = BeautifulSoup(html, "html.parser")
    accordion = soup.select_one(
        'div[data-block-plugin-id="researcher_activities_block"] .accordion'
    )
    if accordion is None:
        accordion = soup.select_one("div.block-researcher-activities-block .accordion")
    if accordion is None:
        return empty_profile

    items = accordion.select(":scope > div.accordion-item")
    if not items:
        items = accordion.select("div.accordion-item")

    item_map = {
        "teaching_affiliations": 0,
        "research_interests": 1,
    }

    extracted = {
        "teaching_affiliations": "",
        "research_interests": "",
        "awards": [],
    }

    for field_name, item_index in item_map.items():
        if item_index >= len(items):
            continue

        body = items[item_index].select_one(BODIES_SELECTOR)
        if body is None:
            continue

        extracted[field_name] = _normalize_text(body.get_text(" ", strip=True))

    if len(items) > 3:
        extracted["awards"] = _parse_awards(items[3])

    return extracted


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
    except Exception:
        return False


def scrape_quantum_people(url: str) -> str:
    """Web scrapes a URL and returns the body html"""
    if not url:
        return
    
    with StealthySession(headless=True, solve_cloudflare=True) as session:
        page = session.fetch(url)
        html = _decode_html(page.body)

    return html
