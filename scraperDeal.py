from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from collections import defaultdict
import time
import urllib.parse

BASE_URL = "https://dealiem.com"

def get_business_urls(driver):
    """Load the main page and extract all business URLs from the business list."""
    driver.get(BASE_URL)
    
    # Wait until the day filter is present (ensures page has loaded)
    wait = WebDriverWait(driver, 10)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "select.filter-item.day-filter")))
    
    # Optionally set the day filter to "Any Day"
    day_filter = driver.find_element(By.CSS_SELECTOR, "select.filter-item.day-filter")
    Select(day_filter).select_by_visible_text("Any Day")
    time.sleep(5)  # allow page update
    
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")
    
    # Each business is linked by an <a> with an href that starts with "/business/"
    links = soup.select("div.business-list a[href^='/business/']")
    business_urls = []
    for a in links:
        href = a.get("href")
        full_url = urllib.parse.urljoin(BASE_URL, href)
        business_urls.append(full_url)
    # Remove duplicates if necessary
    return list(set(business_urls))

def scrape_business_deals(driver, business_url):
    """For a given business page URL, click each day tab and extract deals info and the address."""
    deals_by_day = defaultdict(list)
    
    driver.get(business_url)
    wait = WebDriverWait(driver, 10)
    
    # Wait until the tabs container appears (assumed to have class 'RRT__tabs')
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.RRT__tabs")))
    except Exception as e:
        print(f"Tabs container not found on {business_url} - skipping")
        return None
    
    # Extract the restaurant name
    try:
        restaurant_name = driver.find_element(By.CSS_SELECTOR, "h1.biz-detail-name").text.strip()
    except:
        restaurant_name = "Unknown Restaurant"
    
    # Wait for the address element to be present and extract it.
    try:
        address = driver.find_element(By.CSS_SELECTOR, "p.biz-detail-address a").text.strip()
    except Exception as e:
        address = "Address not found"
        print(f"Address not found for {restaurant_name} at {business_url}")
    
    # Find all the day tabs (assumed to be elements with class "RRT__tab")
    try:
        tabs = driver.find_elements(By.CSS_SELECTOR, "div.RRT__tabs div.RRT__tab")
    except Exception as e:
        print(f"Error finding tabs for {business_url}: {e}")
        return None

    # Loop through each tab to get deals for each day
    for tab in tabs:
        day = tab.text.strip()
        tab_class = tab.get_attribute("class")
        if "disabled" in tab_class:
            # Skip if disabled (no deals for that day)
            print(f"Skipping disabled tab for {day} in {restaurant_name}")
            continue
        
        try:
            # Click the tab to load its deals panel
            tab.click()
            time.sleep(1)  # allow time for the content to update
            
            # Use the aria-controls attribute to get the panel's id
            panel_id = tab.get_attribute("aria-controls")
            panel = wait.until(EC.presence_of_element_located((By.ID, panel_id)))
            
            # Extract deal details from the panel.
            deal_elements = panel.find_elements(By.CSS_SELECTOR, "div.deals-details")
            for deal_el in deal_elements:
                try:
                    time_slot = deal_el.find_element(By.CSS_SELECTOR, "div.time-slots").text.strip()
                except:
                    time_slot = ""
                
                deal_descs = deal_el.find_elements(By.CSS_SELECTOR, "div.deal-description")
                for dd in deal_descs:
                    try:
                        price = dd.find_element(By.CSS_SELECTOR, "div.price-after").text.strip()
                    except:
                        price = ""
                    try:
                        description = dd.find_element(By.CSS_SELECTOR, "div.description").text.strip()
                    except:
                        description = ""
                    if price or description:
                        info = f"{price} - {description}" if price else description
                        if time_slot:
                            info = f"{time_slot}: {info}"
                        deals_by_day[day].append(info)
            print(f"Extracted {len(deals_by_day[day])} deals for {day} at {restaurant_name}")
        except Exception as e:
            print(f"Error processing tab {day} at {restaurant_name}: {e}")
    
    return restaurant_name, address, deals_by_day

def scrape_deals():
    # Set up Chrome options
    options = Options()
    options.add_argument("--headless")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        # Get all business URLs from the main deals page
        business_urls = get_business_urls(driver)
        print(f"Found {len(business_urls)} business URLs")
        
        # Loop through each business and scrape its deals tabs and address
        for url in business_urls:
            print(f"\nProcessing business: {url}")
            result = scrape_business_deals(driver, url)
            if result is None:
                continue
            restaurant_name, address, deals_by_day = result
            print(f"\nRestaurant: {restaurant_name}")
            print(f"Address: {address}")
            for day, deals in deals_by_day.items():
                print(f"  {day}:")
                for deal in deals:
                    print("    ", deal)
            print("-" * 40)
            time.sleep(1)
    
    finally:
        driver.quit()

if __name__ == "__main__":
    scrape_deals()
