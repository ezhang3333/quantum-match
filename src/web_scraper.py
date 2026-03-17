from scrapling.fetchers import StealthySession

def scrape_quantum_people(url):
    with StealthySession(headless=True, solve_cloudflare=True) as session:
        page = session.fetch(url)
        html = page.body.decode("utf-8", errors="replace")

    return html

# add function to clean the html
# add function to create the database, thinking sqlite