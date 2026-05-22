import sys
import os
import time
import json
import psutil
from selenium.webdriver.common.by import By
import undetected_chromedriver as uc

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIES_FILE = os.path.join(BASE_DIR, "cookies.json")

def clean_chrome_processes():
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] in ('chrome.exe', 'chromedriver.exe'):
                proc.terminate()
        except:
            pass
    time.sleep(2)

def main():
    clean_chrome_processes()
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    driver = uc.Chrome(options=options)
    
    try:
        # Load cookies
        driver.get("https://www.alibaba.com/")
        time.sleep(3)
        if os.path.exists(COOKIES_FILE):
            with open(COOKIES_FILE, "r") as f:
                cookies = json.load(f)
            for c in cookies:
                try:
                    driver.add_cookie(c)
                except:
                    pass
            print("Cookies loaded!")
            driver.get("https://www.alibaba.com/")
            time.sleep(3)

        # Navigate to product page
        product_url = "https://www.alibaba.com/product-detail/Bamboo-Stylish-Hot-Selling-Outdoor-Wedding_1601720391858.html?spm=a2700.prosearch.normal_offer.d_image.77ad67af6beA3U&priceId=119fe34b0aa94969bd16e54130d14946"
        driver.get(product_url)
        time.sleep(8)
        
        # Find Contact Supplier button
        buttons = driver.find_elements(By.XPATH, "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'contact supplier')]")
        print(f"Found {len(buttons)} 'contact supplier' buttons.")
        if buttons:
            print("Clicking first button...")
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", buttons[0])
            time.sleep(1)
            buttons[0].click()
            time.sleep(10)
            
            # Print page status
            print(f"Current URL: {driver.current_url}")
            print(f"Window Handles: {len(driver.window_handles)}")
            
            # Dump all iframes and elements
            def inspect_context(path_prefix="Main"):
                # Search for textarea/inputs
                textareas = driver.find_elements(By.TAG_NAME, "textarea")
                inputs = driver.find_elements(By.TAG_NAME, "input")
                divs = driver.find_elements(By.XPATH, "//div[@contenteditable='true']")
                buttons = driver.find_elements(By.TAG_NAME, "button")
                
                print(f"[{path_prefix}] Textareas found: {len(textareas)}")
                for t in textareas:
                    print(f"  - TEXTAREA: name='{t.get_attribute('name')}', id='{t.get_attribute('id')}', placeholder='{t.get_attribute('placeholder')}', class='{t.get_attribute('class')}'")
                
                print(f"[{path_prefix}] ContentEditable divs found: {len(divs)}")
                for d in divs:
                    print(f"  - DIV: id='{d.get_attribute('id')}', class='{d.get_attribute('class')}'")
                
                print(f"[{path_prefix}] Inputs found: {len(inputs)}")
                for i in inputs[:10]:
                    print(f"  - INPUT: type='{i.get_attribute('type')}', name='{i.get_attribute('name')}', id='{i.get_attribute('id')}', placeholder='{i.get_attribute('placeholder')}'")
                
                print(f"[{path_prefix}] Buttons found: {len(buttons)}")
                for b in buttons[:10]:
                    print(f"  - BUTTON: text='{b.text[:30]}', id='{b.get_attribute('id')}', class='{b.get_attribute('class')}'")

                # Scan iframes
                iframes = driver.find_elements(By.TAG_NAME, "iframe")
                print(f"[{path_prefix}] Iframes found: {len(iframes)}")
                for idx, iframe in enumerate(iframes):
                    iframe_id = iframe.get_attribute("id")
                    iframe_class = iframe.get_attribute("class")
                    iframe_src = iframe.get_attribute("src")
                    print(f"[{path_prefix}] Switching to iframe {idx} (id='{iframe_id}', class='{iframe_class}', src='{iframe_src}')")
                    try:
                        driver.switch_to.frame(iframe)
                        inspect_context(f"{path_prefix} -> Iframe {idx}")
                        driver.switch_to.parent_frame()
                    except Exception as e:
                        print(f"  - Error switching: {e}")
                        driver.switch_to.default_content()
            
            inspect_context()
            
    except Exception as e:
        print(f"FATAL ERROR: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
