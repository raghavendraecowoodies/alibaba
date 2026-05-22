import subprocess
import sys
import os
import json
import time
import psutil
import logging
import threading
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "alibaba_inquiry.log")
COOKIES_FILE = os.path.join(BASE_DIR, "cookies.json")

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

def log_step(msg, delay=0):
    logging.info(msg)
    # Force real-time printing in the terminal to avoid stdout buffering issues
    print(f"\n>>> {msg}", flush=True)
    if delay > 0:
        time.sleep(delay)

# --- Helper Functions ---
def wait_el(driver, selectors, timeout=20):
    start = time.time()
    candidate = None
    while time.time() - start < timeout:
        for selector in selectors:
            try:
                el = driver.find_element(*selector)
                if el.is_displayed():
                    return el
                else:
                    candidate = el  # Store as non-displayed fallback
            except:
                pass
        time.sleep(1)
        
    if candidate:
        logging.warning("Returning non-displayed candidate element as fallback.")
        return candidate
    return None

def safe_click(driver, el):
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        time.sleep(0.5)
        el.click()
    except Exception:
        driver.execute_script("arguments[0].click();", el)

def clean_chrome_processes():
    log_step("Cleaning up existing Chrome/Chromedriver processes to prevent lock...")
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] in ('chrome.exe', 'chromedriver.exe'):
                proc.terminate()
        except Exception:
            pass
    time.sleep(2)

def start_browser():
    clean_chrome_processes()
    log_step("Starting Chrome using undetected_chromedriver...")
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    driver = uc.Chrome(options=options)
    return driver

# --- Session Management ---
def load_cookies(driver):
    if os.path.exists(COOKIES_FILE):
        try:
            log_step("Found existing cookies.json. Loading session cookies...")
            driver.get("https://www.alibaba.com/")
            time.sleep(3)
            with open(COOKIES_FILE, "r") as f:
                cookies = json.load(f)
            for c in cookies:
                try:
                    driver.add_cookie(c)
                except Exception:
                    pass
            log_step("Cookies loaded successfully.")
            driver.get("https://www.alibaba.com/")
            time.sleep(3)
            return True
        except Exception as e:
            logging.error(f"Failed to load cookies: {e}")
    return False

def save_cookies(driver):
    try:
        cookies = driver.get_cookies()
        with open(COOKIES_FILE, "w") as f:
            json.dump(cookies, f, indent=4)
        log_step("Cookies saved to cookies.json successfully.")
    except Exception as e:
        logging.error(f"Failed to save cookies: {e}")

def check_login_and_wait(driver):
    log_step("Checking if session is authenticated...")
    cookies_loaded = load_cookies(driver)
    
    if cookies_loaded:
        log_step("Cookies loaded from cookies.json. Proceeding automatically in 5 seconds...")
        time.sleep(5)
        return
        
    # If no cookies, prompt the user for manual login on the first run
    print("\n" + "="*80)
    print("  [FIRST RUN - MANUAL LOGIN REQUIRED]")
    print("  Please log in to your Alibaba.com account in the opened Chrome window.")
    print("  Once you are fully logged in and can see your Alibaba dashboard/home page,")
    print("  return to this console and press [ENTER] to continue...")
    print("="*80 + "\n")
    
    input("Press [ENTER] in this console when you are logged in and ready...")
    
    # Save the fresh session cookies for next time
    save_cookies(driver)

# --- Main Automation Flow ---
def run_automation():
    driver = None
    try:
        driver = start_browser()
        check_login_and_wait(driver)
        
        # Navigate directly to the exact search results URL specified by the user
        target_search_url = "https://www.alibaba.com/search/page?spm=a2700.product_home_fy25.home_login_first_screen_fy23_pc_search_bar.keydown__Enter&SearchScene=proSearch&SearchText=bamboo+chair&pro=true&from=pcHomeContent"
        log_step("Navigating directly to Alibaba Search Results page...")
        driver.get(target_search_url)
        time.sleep(5)
        
        # Wait up to 3 minutes in case a verification CAPTCHA screen is displayed
        log_step("Verifying search results page is loaded...")
        print("\n" + "="*80)
        print("  [VERIFYING RESULTS PAGE]")
        print("  The script is loading the search results page.")
        print("  If a security verification slider / CAPTCHA appears, please solve it.")
        print("  The script will automatically detect the page and proceed instantly!")
        print("="*80 + "\n")
        
        start_wait = time.time()
        search_results_loaded = False
        
        while time.time() - start_wait < 180:
            current_url = driver.current_url
            if "SearchText" in current_url or "bamboo" in current_url or "products/" in current_url:
                log_step("Detected active search results page! Continuing...")
                search_results_loaded = True
                break
            time.sleep(2)
            
        if not search_results_loaded:
            # Debugging info
            log_step(f"[DEBUG] Failed to reach search results page. Current URL: {driver.current_url}")
            log_step(f"[DEBUG] Page Title: {driver.title}")
            raise Exception("Search results page did not load within 3 minutes.")
            
        log_step("Locating the first organic product link...")
        product_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/product-detail/')]")
        if not product_links:
            # Fallback selectors
            product_elements = driver.find_elements(By.CSS_SELECTOR, ".m-gallery-product-item-v2 a, .search-card-info__wrapper a, a.search-card-title-link, a.search-card-e-title, a.search-card-title, a.product-title, a.title, .product-item a, .product-card a")
            product_links = [el for el in product_elements if el.get_attribute("href")]
            
        if not product_links:
            raise Exception("No product links found on the search results page.")
            
        first_product = product_links[0]
        product_url = first_product.get_attribute("href")
        log_step(f"Found first product: {product_url}")
        
        main_handle = driver.current_window_handle
        
        log_step("Opening the product page...")
        safe_click(driver, first_product)
        time.sleep(5)
        
        # Robust tab switching
        new_handle = None
        for handle in driver.window_handles:
            if handle != main_handle:
                new_handle = handle
                break
                
        if new_handle:
            driver.switch_to.window(new_handle)
            log_step("Switched to the new tab containing product details.")
        else:
            log_step("Product details opened in current tab.")
            
        time.sleep(5)
        
        log_step("Searching for 'Contact Supplier' or 'Send Inquiry' button...")
        # Ultra-robust case-insensitive full-text checks using XPath dot (.) selector
        contact_btn = wait_el(driver, [
            (By.XPATH, "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'contact supplier')]"),
            (By.XPATH, "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'send inquiry')]"),
            (By.XPATH, "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'chat now')]"),
            (By.XPATH, "//button[contains(., 'Contact Supplier')]"),
            (By.XPATH, "//a[contains(., 'Contact Supplier')]"),
            (By.XPATH, "//button[contains(., 'Send Inquiry')]"),
            (By.XPATH, "//a[contains(., 'Send Inquiry')]"),
            (By.XPATH, "//button[contains(., 'Chat Now')]"),
            (By.XPATH, "//a[contains(., 'Chat Now')]"),
            (By.CSS_SELECTOR, "a.contact-supplier"),
            (By.CSS_SELECTOR, "button.contact-supplier"),
            (By.CSS_SELECTOR, "a.send-inquiry"),
            (By.CSS_SELECTOR, "button.send-inquiry")
        ], timeout=25)
        
        if not contact_btn:
            raise Exception("Contact Supplier button not found on product page.")
            
        log_step("Clicking Contact Supplier / Send Inquiry...")
        safe_click(driver, contact_btn)
        time.sleep(8)
        
        # Check if clicking opened a new tab/window for the inquiry form
        inquiry_handle = None
        for handle in driver.window_handles:
            if handle not in (main_handle, new_handle):
                inquiry_handle = handle
                break
                
        if inquiry_handle:
            driver.switch_to.window(inquiry_handle)
            log_step("Switched to new tab/window containing the inquiry form.")
            time.sleep(5)
            
        log_step("Locating message textbox (textarea)...")
        textarea = None
        
        # 1. Search directly on the current context page
        textarea = wait_el(driver, [
            (By.XPATH, "//textarea[@name='message']"),
            (By.XPATH, "//textarea[contains(@placeholder, 'Enter your inquiry')]"),
            (By.XPATH, "//textarea[contains(@class, 'ui-textarea')]"),
            (By.TAG_NAME, "textarea")
        ], timeout=10)
        
        # 2. Fallback search inside iframes
        if not textarea:
            log_step("Textarea not found in main document, checking iframes...")
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for i, iframe in enumerate(iframes):
                try:
                    driver.switch_to.frame(iframe)
                    log_step(f"Switched to iframe {i}, checking for textarea...")
                    textarea = wait_el(driver, [
                        (By.XPATH, "//textarea[@name='message']"),
                        (By.XPATH, "//textarea[contains(@placeholder, 'Enter your inquiry')]"),
                        (By.XPATH, "//textarea[contains(@class, 'ui-textarea')]"),
                        (By.TAG_NAME, "textarea")
                    ], timeout=3)
                    if textarea:
                        log_step(f"Found message textarea inside iframe {i}!")
                        break
                    else:
                        driver.switch_to.default_content()
                except Exception:
                    driver.switch_to.default_content()
                    
        if not textarea:
            raise Exception("Inquiry message textarea not found!")
            
        log_step("Entering the custom inquiry message...")
        textarea.clear()
        message = "may this chair available in white color"
        textarea.send_keys(message)
        time.sleep(2)
        
        log_step("Locating inquiry Send/Submit button...")
        send_btn = wait_el(driver, [
            (By.XPATH, "//button[contains(text(), 'Send')]"),
            (By.XPATH, "//button[contains(text(), 'Submit')]"),
            (By.XPATH, "//input[@type='submit']"),
            (By.XPATH, "//button[@type='submit']"),
            (By.XPATH, "//button[@data-role='send-inquiry']"),
            (By.CSS_SELECTOR, ".send-button"),
            (By.CSS_SELECTOR, "button.ui-button-submit")
        ], timeout=10)
        
        if not send_btn:
            raise Exception("Inquiry send button not found!")
            
        log_step("Clicking 'Send'...")
        safe_click(driver, send_btn)
        
        log_step("Inquiry submitted! Waiting 15 seconds for visual confirmation...")
        time.sleep(15)
        log_step("PROCESS COMPLETE.")
        
    except Exception as e:
        logging.critical(f"FATAL ERROR: {e}")
        log_step(f"CRITICAL FAULT: {e}")
    finally:
        if driver:
            log_step("Closing browser...")
            driver.quit()

if __name__ == "__main__":
    run_automation()
