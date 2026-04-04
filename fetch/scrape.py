import requests
from bs4 import BeautifulSoup
import re
import pdfplumber
import io

# -----------------------------
# STEP 1: Google search (simple)
# -----------------------------
from urllib.parse import quote

def search_datasheet(model_query):
    domains = [
        "longi.com",
        "jinkosolar.com",
        "trina-solar.com",
        "canadiansolar.com"
    ]

    headers = {"User-Agent": "Mozilla/5.0"}

    for domain in domains:
        query = f"{model_query} site:{domain} pdf"
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"

        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, "html.parser")

        for link in soup.find_all("a"):
            href = link.get("href", "")
            if "/url?q=" in href and "pdf" in href:
                real_url = href.split("/url?q=")[1].split("&")[0]

                if real_url.startswith("http"):
                    return real_url

    return None


# -----------------------------
# STEP 2: Download + parse PDF
# -----------------------------
def extract_pdf_text(pdf_url):
    res = requests.get(pdf_url)
    with pdfplumber.open(io.BytesIO(res.content)) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text


# -----------------------------
# STEP 3: Extract key specs
# -----------------------------
def extract_specs(text):
    specs = {}

    # Dimensions (example patterns)
    dim_match = re.search(r"(\d{3,4}\s?[xX×]\s?\d{3,4}\s?[xX×]\s?\d{2,3}\s?mm)", text)
    if dim_match:
        specs["dimensions"] = dim_match.group(1)

    # Power (W)
    power_match = re.search(r"(\d{3,4})\s?W", text)
    if power_match:
        specs["power_watts"] = int(power_match.group(1))

    # Efficiency
    eff_match = re.search(r"(\d{1,2}\.\d+)\s?%", text)
    if eff_match:
        specs["efficiency_percent"] = float(eff_match.group(1))

    return specs


# -----------------------------
# STEP 4: Estimate power vs sunlight
# -----------------------------
def estimate_output(power_watts, irradiance):
    """
    power_watts = rated power at 1000 W/m²
    irradiance = actual sunlight W/m²
    """
    return power_watts * (irradiance / 1000)


# -----------------------------
# STEP 5: Price scraping (basic)
# -----------------------------
def get_price(model_query):
    url = f"https://www.google.com/search?q={model_query}+solar+panel+price"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)

    # naive extraction
    prices = re.findall(r"\$\d+", res.text)
    return prices[:3]


# -----------------------------
# MAIN
# -----------------------------
def analyze_panel(model):
    print(f"\nSearching for {model}...\n")

    pdf_url = search_datasheet(model)
    if not pdf_url:
        print("Datasheet not found")
        return

    print("PDF:", pdf_url)

    text = extract_pdf_text(pdf_url)
    specs = extract_specs(text)

    print("\nExtracted Specs:")
    print(specs)

    if "power_watts" in specs:
        for irr in [1000, 800, 600]:
            est = estimate_output(specs["power_watts"], irr)
            print(f"Estimated output at {irr} W/m²: {est:.1f} W")

    prices = get_price(model)
    print("\nSample prices:", prices)


# Example
analyze_panel("LONGi Hi-MO 7 590W")
