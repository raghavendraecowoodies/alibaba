"""
Debug script: visits row 4 and row 5 product pages, saves screenshots + HTML,
and prints every button/link found on each page.
"""
import os, json, time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIES_FILE = os.path.join(BASE_DIR, "cookies.json")

URLS = {
    4: "https://www.alibaba.com/product-detail/Traditional-Handmade-Bamboo-Dining-Chair-Ancient_1601517208256.html?spm=a2700.prosearch.normal_offer.d_image.233f67afYwWd1I&priceId=392dba6c8f354dadbeb1af119abb35b4",
    5: "https://www.alibaba.com/product-detail/Wholesale-Custom-Stackable-Portable-Folding-Bamboo_1601547977909.html?spm=a2700.prosearch.normal_offer.d_image.233f67afYwWd1I&priceId=392dba6c8f354dadbeb1af119abb35b4",
}

def main():
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    driver = uc.Chrome(options=options, version_main=148)
    driver.set_page_load_timeout(120)

    try:
        # Load cookies
        print("Loading alibaba.com ...", flush=True)
        try:
            driver.get("https://www.alibaba.com/")
        except Exception as e:
            print(f"  Page load warning: {str(e)[:80]}", flush=True)
        time.sleep(5)

        if os.path.exists(COOKIES_FILE):
            with open(COOKIES_FILE) as f:
                for c in json.load(f):
                    try:
                        driver.add_cookie(c)
                    except:
                        pass
            print("Cookies loaded.", flush=True)
            try:
                driver.get("https://www.alibaba.com/")
            except Exception as e:
                print(f"  Page load warning: {str(e)[:80]}", flush=True)
            time.sleep(5)

        for row_num, url in URLS.items():
            print(f"\n{'='*60}", flush=True)
            print(f"Row {row_num}: {url[:80]}...", flush=True)
            try:
                driver.get(url)
            except Exception as e:
                print(f"  Page load warning: {str(e)[:80]}", flush=True)
            time.sleep(10)

            # Save screenshot
            ss_path = os.path.join(BASE_DIR, f"debug_row_{row_num}.png")
            driver.save_screenshot(ss_path)
            print(f"  Screenshot saved: {ss_path}", flush=True)

            # Save HTML
            html_path = os.path.join(BASE_DIR, f"debug_row_{row_num}.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print(f"  HTML saved: {html_path}", flush=True)

            # Find all buttons
            print("\n  --- BUTTONS ---", flush=True)
            buttons = driver.find_elements(By.TAG_NAME, "button")
            for b in buttons:
                try:
                    txt = b.text.strip()[:60]
                    cls = (b.get_attribute("class") or "")[:80]
                    tid = b.get_attribute("data-testid") or ""
                    bid = b.get_attribute("id") or ""
                    vis = b.is_displayed()
                    if txt or tid:
                        print(f"    BUTTON text='{txt}' | class='{cls}' | testid='{tid}' | id='{bid}' | visible={vis}", flush=True)
                except:
                    pass

            # Find all links with inquiry-related text
            print("\n  --- INQUIRY LINKS/ELEMENTS ---", flush=True)
            for tag in ["a", "div", "span"]:
                els = driver.find_elements(By.TAG_NAME, tag)
                for el in els:
                    try:
                        txt = el.text.strip()[:60]
                        if any(kw in txt.lower() for kw in ["inquiry", "contact supplier", "chat now", "send inquiry"]):
                            cls = (el.get_attribute("class") or "")[:80]
                            tid = el.get_attribute("data-testid") or ""
                            eid = el.get_attribute("id") or ""
                            vis = el.is_displayed()
                            print(f"    <{tag}> text='{txt}' | class='{cls}' | testid='{tid}' | id='{eid}' | visible={vis}", flush=True)
                    except:
                        pass

            # Find data-testid with INQUIRY
            print("\n  --- data-testid INQUIRY elements ---", flush=True)
            els = driver.find_elements(By.XPATH, "//*[contains(@data-testid, 'nquiry') or contains(@data-testid, 'nquir') or contains(@data-testid, 'INQUIRY')]")
            for el in els:
                try:
                    print(f"    tag={el.tag_name} testid='{el.get_attribute('data-testid')}' text='{el.text[:40]}' visible={el.is_displayed()}", flush=True)
                except:
                    pass

    except Exception as e:
        print(f"FATAL: {e}", flush=True)
    finally:
        print("\nDone. Quitting browser.", flush=True)
        driver.quit()

if __name__ == "__main__":
    main()
