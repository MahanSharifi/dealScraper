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

import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firebase app with your service account key
cred = credentials.Certificate("swipe.json")
firebase_admin.initialize_app(cred)

# Initialize Firestore client
db = firestore.client()

def push_deals_of_the_day(deals_data, business_url, restaurant_name):
    # Use the unique portion of the business URL (after '/business/') as the document ID.
    unique_id = business_url.split("/business/")[-1]
    deals_collection = db.collection('dealsOfTheDay')
    doc_ref = deals_collection.document(unique_id)
    
    # Check if a document with this ID already exists.
    if doc_ref.get().exists:
        print(f"Document for '{restaurant_name}' (ID: {unique_id}) already exists. Skipping push.")
    else:
        doc_ref.set(deals_data)
        print("Deals data pushed with document ID:", doc_ref.id)

def build_deals_model(restaurant_name, business_url, address, deals_by_day, images):
    # Mapping from abbreviated day names to full day names.
    day_mapping = {
        "Sun": "Sunday",
        "Mon": "Monday",
        "Tue": "Tuesday",
        "Wed": "Wednesday",
        "Thurs": "Thursday",
        "Fri": "Friday",
        "Sat": "Saturday"
    }
    
    deals_model = {}
    for abbr, full_day in day_mapping.items():
        # For each day, store the deals (an array of deal strings) under "description"
        deals_list = deals_by_day.get(abbr, [])
        deals_model[full_day] = {"description": deals_list}
    
    # Add additional fields
    deals_model["name"] = restaurant_name
    deals_model["address"] = address
    deals_model["url"] = business_url
    deals_model["images"] = images  # Array of image URLs

    return deals_model

BASE_URL = "https://dealiem.com"

def get_business_urls(driver):
    """Load the main page and extract all business URLs from the business list."""
    driver.get(BASE_URL)
    wait = WebDriverWait(driver, 10)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "select.filter-item.day-filter")))
    
    day_filter = driver.find_element(By.CSS_SELECTOR, "select.filter-item.day-filter")
    Select(day_filter).select_by_visible_text("Any Day")
    time.sleep(5)  # allow page update
    
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")
    links = soup.select("div.business-list a[href^='/business/']")
    
    business_urls = []
    for a in links:
        href = a.get("href")
        full_url = urllib.parse.urljoin(BASE_URL, href)
        business_urls.append(full_url)
    
    return list(set(business_urls))

def extract_images(driver):
    """
    Extract all image URLs from the business page carousel.
    Assumes images have the class 'carousel-img'.
    """
    images = []
    try:
        img_elements = driver.find_elements(By.CSS_SELECTOR, "img.carousel-img")
        images = [img.get_attribute("src") for img in img_elements if img.get_attribute("src")]
    except Exception as e:
        print("Error extracting images:", e)
    return images

def scrape_business_deals(driver, business_url):
    """For a given business page URL, click each day tab and extract deals info, address, and images."""
    deals_by_day = defaultdict(list)
    
    driver.get(business_url)
    wait = WebDriverWait(driver, 10)
    
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.RRT__tabs")))
    except Exception as e:
        print(f"Tabs container not found on {business_url} - skipping")
        return None
    
    try:
        restaurant_name = driver.find_element(By.CSS_SELECTOR, "h1.biz-detail-name").text.strip()
    except:
        restaurant_name = "Unknown Restaurant"
    
    try:
        address = driver.find_element(By.CSS_SELECTOR, "p.biz-detail-address a").text.strip()
    except Exception as e:
        address = "Address not found"
        print(f"Address not found for {restaurant_name} at {business_url}")
    
    # Extract images from the carousel
    images = extract_images(driver)
    
    try:
        tabs = driver.find_elements(By.CSS_SELECTOR, "div.RRT__tabs div.RRT__tab")
    except Exception as e:
        print(f"Error finding tabs for {business_url}: {e}")
        return None

    for tab in tabs:
        day = tab.text.strip()  # e.g., "Sun", "Mon", etc.
        tab_class = tab.get_attribute("class")
        if "disabled" in tab_class:
            print(f"Skipping disabled tab for {day} in {restaurant_name}")
            continue
        
        try:
            tab.click()
            time.sleep(1)
            panel_id = tab.get_attribute("aria-controls")
            panel = wait.until(EC.presence_of_element_located((By.ID, panel_id)))
            
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
                        info = f"{time_slot}: {price} - {description}" if time_slot else f"{price} - {description}"
                        deals_by_day[day].append(info)
            print(f"Extracted {len(deals_by_day[day])} deals for {day} at {restaurant_name}")
        except Exception as e:
            print(f"Error processing tab {day} at {restaurant_name}: {e}")
    
    return restaurant_name, address, deals_by_day, images

def scrape_deals():
    options = Options()
    options.add_argument("--headless")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        business_urls = get_business_urls(driver)
        print(f"Found {len(business_urls)} business URLs")
        
        for url in business_urls:
            print(f"\nProcessing business: {url}")
            result = scrape_business_deals(driver, url)
            if result is None:
                continue
            restaurant_name, address, deals_by_day, images = result
            
            print(f"\nRestaurant: {restaurant_name}")
            print(f"Address: {address}")
            for day, deals in deals_by_day.items():
                print(f"  {day}:")
                for deal in deals:
                    print("    ", deal)
            print("  Images:")
            for img in images:
                print("    ", img)
            print("-" * 40)
            
            deals_data = build_deals_model(restaurant_name, url, address, deals_by_day, images)
            push_deals_of_the_day(deals_data, url, restaurant_name)
            time.sleep(1)
    
    finally:
        driver.quit()

if __name__ == "__main__":
    scrape_deals()
