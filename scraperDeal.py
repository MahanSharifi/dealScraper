from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time

def scrape_deals():
    # Set up Chrome options
    options = Options()
    options.add_argument("--headless")  # run headless (without GUI)
    
    # Initialize WebDriver
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        # Load the page (change URL as needed)
        driver.get("https://dealiem.com/")
        
        # Wait for the page to load completely
        time.sleep(5)
        
        # Get the page source
        html = driver.page_source
        
        # Parse the HTML with BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        
        # Find all the deal items
        deal_items = soup.select("div.deal-item")
        
        # Loop through each deal item and print the restaurant name and its deals
        for deal in deal_items:
            # Extract the restaurant name from the element with class "biz-name"
            name_tag = deal.find("h1", class_="biz-name")
            restaurant_name = name_tag.get_text(strip=True) if name_tag else "No name"
            
            # Extract the deal details: price and description
            deal_descriptions = deal.select(".deal-description")
            deals = []
            for dd in deal_descriptions:
                price_tag = dd.find("div", class_="price-after")
                desc_tag = dd.find("div", class_="description")
                price = price_tag.get_text(strip=True) if price_tag else ""
                desc_text = desc_tag.get_text(strip=True) if desc_tag else ""
                # Only add if there's content
                if price or desc_text:
                    deals.append(f"{price} - {desc_text}".strip(" -"))
            
            # Print restaurant name and its deals
            print("Restaurant:", restaurant_name)
            if deals:
                print("Deals:")
                for d in deals:
                    print("  ", d)
            else:
                print("No deal details found.")
            print("-" * 40)
    finally:
        driver.quit()

if __name__ == "__main__":
    scrape_deals()

