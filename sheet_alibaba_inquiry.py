import sys
import os
import time
import json
import psutil
import logging
import gspread
from google.oauth2.service_account import Credentials
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc

# --- Bootstrap: write secrets from env vars to disk (used in Docker) ---
_creds = os.environ.get('CREDENTIALS_JSON')
if _creds:
    with open('/app/instagram-credentials.json', 'w') as f:
        f.write(_creds)

_cookies = os.environ.get('COOKIES_JSON')
if _cookies:
    with open('/app/cookies.json', 'w') as f:
        f.write(_cookies)

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "sheet_alibaba_inquiry.log")

# COOKIES_FILE: check environment variable first, then fallback to local directory
COOKIES_FILE = os.getenv("COOKIES_FILE")
if not COOKIES_FILE:
    COOKIES_FILE = os.path.join(BASE_DIR, "cookies.json")

# CREDENTIALS_FILE: check environment variable first (either CREDENTIALS_FILE or GOOGLE_APPLICATION_CREDENTIALS)
CREDENTIALS_FILE = os.getenv("CREDENTIALS_FILE") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if not CREDENTIALS_FILE or not os.path.exists(CREDENTIALS_FILE):
    local_path = os.path.join(BASE_DIR, "instagram-credentials.json")
    default_win_path = r"C:\Users\DELL\Desktop\linkedin_outreach\instagram-credentials.json"
    if os.path.exists(local_path):
        CREDENTIALS_FILE = local_path
    elif os.path.exists(default_win_path):
        CREDENTIALS_FILE = default_win_path
    else:
        CREDENTIALS_FILE = local_path

SPREADSHEET_ID = "1W5GG30XAlp_qdm5cUwA53LFMnwItS2hG1Rbq7b9CZgM"
INQUIRY_MESSAGE = "what is the cost of this product"

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

def log(msg):
    logging.info(msg)
    try:
        print(f"\n>>> {msg}", flush=True)
    except UnicodeEncodeError:
        print(f"\n>>> {msg.encode('ascii', 'replace').decode()}", flush=True)

# --- Kill old Chrome processes ---
# --- Kill old Chrome processes ---
def clean_chrome_processes():
    log("Killing old Chrome/Chromedriver processes...")
    for proc in psutil.process_iter(['name']):
        try:
            name = proc.info['name']
            if name in ('chrome.exe', 'chromedriver.exe', 'chrome', 'chromedriver'):
                proc.terminate()
        except:
            pass
    time.sleep(3)

# --- Start undetected Chrome ---
def start_browser():
    clean_chrome_processes()
    log("Starting Chrome...")
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    # Docker/Linux headless environment optimization
    if os.getenv("DOCKER_ENV") or sys.platform.startswith("linux"):
        log("Running in Docker/Linux environment. Applying sandboxing and display workarounds...")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-images")
        options.add_argument("--blink-settings=imagesEnabled=false")
        options.add_argument("--memory-pressure-off")
        options.add_argument("--max_old_space_size=256")
        options.add_argument("--single-process")
        if os.getenv("CHROME_HEADLESS"):
            options.add_argument("--headless=new")
            
    try:
        if os.getenv("DOCKER_ENV") or sys.platform.startswith("linux"):
            driver = uc.Chrome(options=options, version_main=148)
        else:
            driver = uc.Chrome(options=options, version_main=148)
    except Exception as e:
        log(f"Warning starting Chrome: {e}. Attempting standard initialization...")
        driver = uc.Chrome(options=options)
        
    # Long timeout so slow Alibaba pages don't crash the session
    driver.set_page_load_timeout(120)
    return driver

# --- Safe navigate (ignores timeout if page partially loads) ---
def safe_get(driver, url, wait=6):
    try:
        driver.get(url)
    except Exception as e:
        log(f"Page load warning (continuing): {str(e)[:100]}")
    time.sleep(wait)

# --- Check and wait for CAPTCHA/Verification screen ---
def check_and_wait_for_captcha(driver, timeout=180):
    start_time = time.time()
    captcha_detected = False
    
    while time.time() - start_time < timeout:
        title = (driver.title or "").lower()
        page_source = (driver.page_source or "").lower()
        
        # Detect captcha signatures
        if "captcha" in title or "verification" in title or "sec-cpt" in page_source or "robot" in page_source:
            if not captcha_detected:
                log("⚠️ CAPTCHA/Verification detected! Please solve the slider/CAPTCHA in the opened Chrome window manually.")
                print("\n" + "="*80)
                print("  [CAPTCHA DETECTED - USER INTERVENTION REQUIRED]")
                print("  Alibaba has displayed a verification / security slider.")
                print("  Please switch to the opened Chrome window and solve it.")
                print("  The script will automatically detect when it is solved and resume.")
                print("="*80 + "\n", flush=True)
                captcha_detected = True
            time.sleep(3)
        else:
            if captcha_detected:
                log("✅ CAPTCHA solved! Continuing with the product page...")
                time.sleep(3)
            return True
            
    log("❌ Timeout waiting for CAPTCHA to be solved.")
    return False

# --- Load cookies and verify login ---
def load_and_verify_cookies(driver):
    if not os.path.exists(COOKIES_FILE):
        log("ERROR: cookies.json not found! Run refresh_login.py first.")
        return False

    log("Loading cookies from cookies.json...")
    safe_get(driver, "https://www.alibaba.com/", wait=5)

    with open(COOKIES_FILE, "r") as f:
        cookies = json.load(f)
    for c in cookies:
        try:
            driver.add_cookie(c)
        except:
            pass

    log("Cookies injected. Refreshing page...")
    safe_get(driver, "https://www.alibaba.com/", wait=7)

    # Verify login by checking page source for account indicators
    page_src = driver.page_source
    if "Sign in" in page_src and "Create account" in page_src and "myAccount" not in page_src:
        log("WARNING: Not logged in! Cookies may be expired. Please run refresh_login.py again.")
        return False

    log("Login verified successfully!")
    return True

# --- Click element safely ---
def safe_click(driver, el):
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        time.sleep(0.8)
        el.click()
    except:
        driver.execute_script("arguments[0].click();", el)

# --- Find inquiry button on product page ---
def find_inquiry_button(driver, timeout=20):
    # Priority 1: data-testid attribute (most reliable)
    selectors = [
        (By.XPATH, "//*[@data-testid='customizationSkuSummary-INQUIRY']"),
        (By.XPATH, "//*[contains(@data-testid, 'INQUIRY')]"),
        (By.XPATH, "//button[contains(@class, 'id-') and .//span[contains(text(),'Contact') or contains(text(),'Inquiry')]]"),
        (By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'contact supplier')]"),
        (By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'send inquiry')]"),
        (By.XPATH, "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'contact supplier')]"),
        (By.XPATH, "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'send inquiry')]"),
    ]
    start = time.time()
    while time.time() - start < timeout:
        for sel in selectors:
            try:
                el = driver.find_element(*sel)
                if el.is_displayed():
                    return el
            except:
                pass
        time.sleep(1)
    return None

# --- Find textarea in current context (page or iframe) ---
def find_textarea_in_context(driver):
    selectors = [
        (By.XPATH, "//textarea[@name='message']"),
        (By.XPATH, "//textarea[@name='content']"),
        (By.XPATH, "//textarea[contains(@placeholder, 'nquiry')]"),
        (By.XPATH, "//textarea[contains(@placeholder, 'essage')]"),
        (By.XPATH, "//textarea[contains(@placeholder, 'cost')]"),
        (By.XPATH, "//textarea[contains(@placeholder, 'price')]"),
        (By.XPATH, "//textarea[contains(@placeholder, 'type') or contains(@placeholder, 'Type')]"),
        (By.XPATH, "//textarea[contains(@placeholder, 'Enter')]"),
        (By.TAG_NAME, "textarea"),
        (By.XPATH, "//div[@contenteditable='true']"),
    ]
    for sel in selectors:
        try:
            el = driver.find_element(*sel)
            if el.is_displayed():
                return el
        except:
            pass
    return None

# --- Find company name on product page ---
def find_company_name(driver):
    selectors = [
        (By.XPATH, "//a[contains(@class, 'company-name')]"),
        (By.XPATH, "//div[contains(@class, 'company-name')]"),
        (By.XPATH, "//*[@class='company-name']"),
        (By.XPATH, "//a[contains(@href, 'company_profile')]"),
        (By.XPATH, "//*[contains(@class, 'supplier-name')]"),
    ]
    for sel in selectors:
        try:
            el = driver.find_element(*sel)
            text = el.text.strip()
            if text:
                return text
        except:
            pass
    return None

# --- Activate chat contact ---
def activate_chat_contact(driver, company_name=None):
    search_terms = []
    if company_name:
        words = [w.strip() for w in company_name.split() if len(w.strip()) > 2]
        if words:
            search_terms.append(words[0])
            if len(words) > 1:
                search_terms.append(words[1])
    
    # Common selectors for chat contact list items
    selectors = [
        (By.XPATH, "//*[contains(@class, 'session-item') or contains(@class, 'contact-item')]"),
        (By.XPATH, "//*[contains(@class, 'contact-list')]//li"),
        (By.XPATH, "//*[contains(@class, 'session-list')]//li"),
        (By.XPATH, "//*[contains(@class, 'session-item')]"),
        (By.XPATH, "//*[contains(@class, 'contact-item')]"),
    ]
    
    # Try searching by company name words first
    for term in search_terms:
        try:
            xpath = f"//*[contains(text(), '{term}') or contains(@title, '{term}')]"
            els = driver.find_elements(By.XPATH, xpath)
            for el in els:
                if el.is_displayed():
                    log(f"Found contact element matching term '{term}'. Clicking to activate...")
                    safe_click(driver, el)
                    time.sleep(3)
                    return True
        except:
            pass
            
    # Try clicking the first contact list item
    for sel in selectors:
        try:
            els = driver.find_elements(*sel)
            for el in els:
                if el.is_displayed():
                    log("Found a contact list item. Clicking to activate...")
                    safe_click(driver, el)
                    time.sleep(3)
                    return True
        except:
            pass
            
    return False

# --- Comprehensive search: page + all iframes ---
def find_textarea_anywhere(driver):
    # 1. Check main document
    el = find_textarea_in_context(driver)
    if el:
        log("Found textarea in main document!")
        return el, "main"

    # 2. Search all top-level iframes
    try:
        driver.switch_to.default_content()
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        log(f"Checking {len(iframes)} iframes for textarea...")
        for idx in range(len(iframes)):
            try:
                driver.switch_to.default_content()
                iframes_fresh = driver.find_elements(By.TAG_NAME, "iframe")
                if idx >= len(iframes_fresh):
                    continue
                driver.switch_to.frame(iframes_fresh[idx])
                el = find_textarea_in_context(driver)
                if el:
                    log(f"Found textarea in iframe #{idx}!")
                    # Keep iframe context and return immediately
                    return el, f"iframe_{idx}"
                # Check nested iframes inside this one
                nested = driver.find_elements(By.TAG_NAME, "iframe")
                for n_idx in range(len(nested)):
                    try:
                        driver.switch_to.default_content()
                        iframes_fresh = driver.find_elements(By.TAG_NAME, "iframe")
                        if idx >= len(iframes_fresh):
                            break
                        driver.switch_to.frame(iframes_fresh[idx])
                        nested_fresh = driver.find_elements(By.TAG_NAME, "iframe")
                        if n_idx >= len(nested_fresh):
                            break
                        driver.switch_to.frame(nested_fresh[n_idx])
                        el = find_textarea_in_context(driver)
                        if el:
                            log(f"Found textarea in nested iframe #{idx}>{n_idx}!")
                            # Keep nested iframe context and return immediately
                            return el, f"iframe_{idx}_nested_{n_idx}"
                    except:
                        pass
            except Exception as e:
                log(f"Error scanning iframe {idx}: {e}")
    except Exception as e:
        log(f"Iframe scan error: {e}")
    
    # If not found, switch back to default content
    try:
        driver.switch_to.default_content()
    except:
        pass
    return None, None

# --- Find and click Send button ---
def find_send_button(driver):
    selectors = [
        (By.XPATH, "//button[normalize-space(text())='Send']"),
        (By.XPATH, "//button[normalize-space(text())='Submit']"),
        (By.XPATH, "//button[contains(text(), 'Send')]"),
        (By.XPATH, "//button[contains(text(), 'Submit')]"),
        (By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'send')]"),
        (By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'submit')]"),
        (By.XPATH, "//input[@type='submit']"),
        (By.XPATH, "//button[@type='submit']"),
        (By.XPATH, "//*[contains(@class, 'send') and (self::button or self::a)]"),
        (By.XPATH, "//*[contains(@class, 'submit') and (self::button or self::a)]"),
    ]
    for sel in selectors:
        try:
            el = driver.find_element(*sel)
            if el.is_displayed():
                return el
        except:
            pass
    return None

# --- Main automation ---
def run():
    # --- Step 1: Read Google Sheet ---
    log("Connecting to Google Sheets...")
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    try:
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_ID).sheet1
        records = sheet.get_all_records()
        headers = sheet.row_values(1)
        log(f"Got {len(records)} records. Headers: {headers}")
    except Exception as e:
        log(f"FATAL: Cannot access Google Sheet: {e}")
        return

    # Find status and message columns
    try:
        status_col = headers.index("status") + 1
    except ValueError:
        log("ERROR: No 'status' column found!")
        return

    try:
        message_col = headers.index("message") + 1
    except ValueError:
        log("WARNING: No 'message' column found — message will not be recorded.")
        message_col = None

    # Get pending rows
    pending = []
    for idx, row in enumerate(records):
        row_num = idx + 2
        url = row.get("product", "").strip()
        status = str(row.get("status", "")).strip().lower()
        if url and status != "done":
            pending.append({"row_num": row_num, "url": url})

    if not pending:
        log("No pending rows. All done!")
        return

    log(f"Found {len(pending)} rows to process.")

    # --- Step 2: Start Browser and Login ---
    driver = start_browser()
    try:
        logged_in = load_and_verify_cookies(driver)
        if not logged_in:
            log("Aborting: Not logged in. Please run refresh_login.py and try again.")
            return

        # --- Step 3: Process each product URL ---
        for item in pending:
            row_num = item["row_num"]
            product_url = item["url"]
            log(f"--- Processing Row {row_num}: {product_url}")

            try:
                original_handle = driver.current_window_handle

                 # Navigate to product page
                log("Opening product page...")
                safe_get(driver, product_url, wait=8)
                
                # Check and wait for CAPTCHA if it appears
                if not check_and_wait_for_captcha(driver):
                    raise Exception("Failed to bypass CAPTCHA.")
                
                # Get company name
                company_name = find_company_name(driver)
                log(f"Extracted supplier company name: {company_name}")

                # Save screenshot for debugging
                driver.save_screenshot(os.path.join(BASE_DIR, f"row_{row_num}_product.png"))

                # Find and click inquiry button
                log("Looking for Contact Supplier / Inquiry button...")
                inq_btn = find_inquiry_button(driver, timeout=25)
                if not inq_btn:
                    raise Exception("Inquiry button not found on page!")

                log(f"Found inquiry button: {inq_btn.text[:40]}")
                safe_click(driver, inq_btn)
                log("Clicked inquiry button. Waiting for chat window to load...")
                time.sleep(12)

                # Check for new tab
                new_handle = None
                for h in driver.window_handles:
                    if h != original_handle:
                        new_handle = h
                        break

                if new_handle:
                    driver.switch_to.window(new_handle)
                    log(f"Switched to new tab: {driver.current_url}")
                    time.sleep(5)
                else:
                    log(f"Same tab, current URL: {driver.current_url}")

                driver.save_screenshot(os.path.join(BASE_DIR, f"row_{row_num}_after_click.png"))

                # The inquiry button opens the Alibaba Chat (onetalk) window
                # It's loaded inside #weblite-iframe (src: onetalk.alibaba.com)
                log("Searching for chat message input in weblite iframe...")
                chat_input = None
                chat_input_location = None

                # Strategy 1: Find the weblite-iframe by id or class and switch into it
                driver.switch_to.default_content()
                try:
                    weblite = None
                    # Try by id
                    try:
                        weblite = driver.find_element(By.ID, "#weblite-iframe")
                    except:
                        pass
                    # Try by class
                    if not weblite:
                        try:
                            weblite = driver.find_element(By.CSS_SELECTOR, ".weblite-iframe")
                        except:
                            pass
                    # Try by src pattern
                    if not weblite:
                        for iframe in driver.find_elements(By.TAG_NAME, "iframe"):
                            src = iframe.get_attribute("src") or ""
                            style = iframe.get_attribute("style") or ""
                            if "onetalk" in src or "weblite" in src:
                                weblite = iframe
                                log(f"Found weblite iframe by src: {src[:60]}")
                                break
                            # Also check if iframe is visible (not display:none)
                            if "display: none" not in style and src and "alibaba" in src:
                                weblite = iframe
                                log(f"Found visible alibaba iframe: {src[:60]}")
                                break

                    if weblite:
                        log("Switching into weblite/chat iframe...")
                        driver.switch_to.frame(weblite)
                        time.sleep(3)
                        driver.save_screenshot(os.path.join(BASE_DIR, f"row_{row_num}_inside_iframe.png"))

                        # Look for message input in chat UI
                        chat_selectors = [
                            (By.XPATH, "//textarea"),
                            (By.XPATH, "//div[@contenteditable='true']"),
                            (By.XPATH, "//input[@type='text']"),
                            (By.XPATH, "//*[@placeholder]"),
                        ]
                        
                        # Helper to search for input
                        def get_input():
                            for sel in chat_selectors:
                                try:
                                    els = driver.find_elements(*sel)
                                    for el in els:
                                        if el.is_displayed():
                                            return el
                                except:
                                    pass
                            return None
                            
                        chat_input = get_input()
                        if chat_input:
                            chat_input_location = "weblite_iframe"
                        else:
                            # Try activating contact
                            log("Chat input not found in weblite. Trying to activate contact list item...")
                            if activate_chat_contact(driver, company_name):
                                time.sleep(2)
                                chat_input = get_input()
                                if chat_input:
                                    chat_input_location = "weblite_iframe_after_activation"
                                    
                        # Check nested iframes inside weblite
                        if not chat_input:
                            log("Checking nested iframes inside weblite...")
                            nested_iframes = driver.find_elements(By.TAG_NAME, "iframe")
                            for n_iframe in nested_iframes:
                                try:
                                    driver.switch_to.frame(n_iframe)
                                    chat_input = get_input()
                                    if chat_input:
                                        chat_input_location = "weblite_nested_iframe"
                                        break
                                    driver.switch_to.parent_frame()
                                except:
                                    try:
                                        driver.switch_to.default_content()
                                        if weblite:
                                            driver.switch_to.frame(weblite)
                                    except:
                                        pass
                except Exception as ie:
                    log(f"Weblite iframe approach error: {ie}")

                # Strategy 2: Fallback - scan all iframes
                if not chat_input:
                    log("Weblite approach failed. Scanning all iframes...")
                    driver.switch_to.default_content()
                    textarea_result, location = find_textarea_anywhere(driver)
                    if textarea_result:
                        chat_input = textarea_result
                        chat_input_location = location

                if not chat_input:
                    # Save debug info
                    driver.switch_to.default_content()
                    with open(os.path.join(BASE_DIR, f"row_{row_num}_debug.html"), "w", encoding="utf-8") as f:
                        f.write(driver.page_source)
                    raise Exception(f"Chat input not found! Check row_{row_num}_after_click.png")

                log(f"Chat input found ({chat_input_location})! Typing message...")
                try:
                    chat_input.clear()
                except:
                    pass
                chat_input.click()
                time.sleep(0.5)
                chat_input.send_keys(INQUIRY_MESSAGE)
                time.sleep(2)
                driver.save_screenshot(os.path.join(BASE_DIR, f"row_{row_num}_message_typed.png"))
                log(f"Message typed. Pressing Enter to send...")

                # Send via Enter key (chat-style) or find Send button
                sent = False
                # Try clicking a Send button first
                send_btn = find_send_button(driver)
                if send_btn:
                    log(f"Found Send button. Clicking...")
                    safe_click(driver, send_btn)
                    sent = True
                else:
                    # Press Enter to send (standard chat behavior)
                    chat_input.send_keys(Keys.RETURN)
                    log("Sent via Enter key!")
                    sent = True

                time.sleep(8)
                driver.switch_to.default_content()
                driver.save_screenshot(os.path.join(BASE_DIR, f"row_{row_num}_sent.png"))
                log("Inquiry/message submitted!")

                # Update Google Sheet — write message and status
                if message_col:
                    sheet.update_cell(row_num, message_col, INQUIRY_MESSAGE)
                    log(f"Row {row_num} message column updated with sent message.")
                sheet.update_cell(row_num, status_col, "done")
                log(f"Row {row_num} updated to 'done' in Google Sheet!")

                # Close extra tabs
                driver.switch_to.default_content()
                for h in list(driver.window_handles):
                    if h != original_handle:
                        driver.switch_to.window(h)
                        driver.close()
                driver.switch_to.window(original_handle)

            except Exception as e:
                log(f"ERROR on Row {row_num}: {e}")
                driver.save_screenshot(os.path.join(BASE_DIR, f"row_{row_num}_error.png"))
                try:
                    driver.switch_to.default_content()
                    for h in list(driver.window_handles):
                        if h != original_handle:
                            driver.switch_to.window(h)
                            driver.close()
                    driver.switch_to.window(original_handle)
                except:
                    pass

    except Exception as e:
        log(f"FATAL ERROR: {e}")
    finally:
        log("Closing browser...")
        try:
            driver.quit()
        except:
            pass

if __name__ == "__main__":
    run()
