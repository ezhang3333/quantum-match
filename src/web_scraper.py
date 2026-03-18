from scrapling.fetchers import StealthySession
from constants import QUANTUM_SCIENTIST_DATABASE_URL
from bs4 import BeautifulSoup
from pprint import pprint

def scrape_quantum_people(url: str) -> str:
    """Web scrapes a URL and returns the body html"""
    if not url:
        return
    
    with StealthySession(headless=True, solve_cloudflare=True) as session:
        page = session.fetch(url)
        html = page.body.decode("utf-8", errors="replace")

    return html


def extract_from_quantum_zeitgeist(html):
    """
    Parses the quantum people table from given html. This function expects
    the html to be from the QUANTUM_SCIENTIST_DATABASE_URL

    Args:
        html: HTML string from the quantum zeitgeist page

    Returns:
        A dictionary indexed by full name, each value containing:
            - full_name
            - institution
            - link
            - summary
    """
    if not html:
        return
    
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.select("figure.wp-block-table table")

    if len(tables) > 1:
        raise ValueError(f"Expected 1 table, found {len(tables)} instead. Please verify which table you are trying to extract.")
    
    quantum_table = tables[0]

    quantum_table_header = quantum_table.find("thead")
    quantum_table_people = quantum_table.find("tbody")

    table_headers = []
    quantum_people = {}

    for header in quantum_table_header.children:
        table_headers.append(header.text)
    
    for person in quantum_table_people.children:
        attributes = person.find_all("td")
        full_name = attributes[0].get_text(strip=True)
        institution = attributes[1].get_text(strip=True)
        link = attributes[2].find("a")["href"]
        summary = attributes[3].get_text(strip=True)

        new_person = {
            "full_name" : full_name,
            "institution" : institution,
            "link" : link,
            "summary" : summary
        }

        # going to index into dictionary by full name since table size is small 
        # and no 2 entries should have the same full name
        quantum_people[f"{full_name}"] = new_person
    
    return quantum_people
    

def test():
    html = scrape_quantum_people(QUANTUM_SCIENTIST_DATABASE_URL)
    quantum_people = extract_from_quantum_zeitgeist(html)

    pprint(quantum_people)

if __name__ == "__main__":
    test()
    
# add function to create the database, thinking sqlite
# remove the pretty print import after dont testing