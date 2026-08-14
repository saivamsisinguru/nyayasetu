import os
import time
from playwright.sync_api import sync_playwright, expect

BASE_URL = "http://127.0.0.1:5000"
SCREENSHOT_DIR = "tests/screenshots"

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def check_text(page, selector, expected, exact=False):
    """Check if element text contains expected (or equals if exact=True)."""
    locator = page.locator(selector).first
    try:
        locator.wait_for(timeout=5000)
        text = locator.inner_text().strip()
        if exact:
            condition = text == expected
        else:
            condition = expected.lower() in text.lower()
        if condition:
            print(f"✅ {selector}: '{text}'")
        else:
            print(f"❌ {selector}: expected '{expected}', got '{text}'")
        return condition
    except Exception as e:
        print(f"❌ {selector}: error - {e}")
        return False

def check_color(page, selector, css_property, expected_rgb):
    """Check computed CSS color of an element."""
    locator = page.locator(selector).first
    try:
        color = locator.evaluate(f"el => getComputedStyle(el).{css_property}")
        if color == expected_rgb:
            print(f"✅ {selector} {css_property}: {color}")
        else:
            print(f"❌ {selector} {css_property}: expected {expected_rgb}, got {color}")
        return color == expected_rgb
    except Exception as e:
        print(f"❌ {selector}: error - {e}")
        return False

def run_tests():
    ensure_dir(SCREENSHOT_DIR)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Visible browser
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        # ---------- 1. HOME PAGE ----------
        print("\n=== 1. HOME PAGE ===")
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")

        check_text(page, ".navbar-brand", "NyayaSetu")
        check_text(page, "h1", "Legal Advice")
        check_color(page, "body", "backgroundColor", "rgb(10, 22, 40)")           # bg-dark
        check_color(page, ".navbar", "backgroundColor", "rgb(13, 31, 60)")        # bg-card
        check_color(page, ".btn-accent", "backgroundColor", "rgb(255, 107, 53)")  # accent
        page.screenshot(path=f"{SCREENSHOT_DIR}/home.png")

        # ---------- 2. CLIENT LOGIN + ONBOARDING ----------
        print("\n=== 2. CLIENT LOGIN + ONBOARDING ===")
        page.goto(f"{BASE_URL}/login")
        page.fill("input[name='phone']", "9990001111")
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")

        # If onboarding appears (new user)
        if "onboarding" in page.url:
            page.fill("input[name='name']", "Test Client")
            page.fill("input[name='email']", "testclient@example.com")
            page.fill("input[name='city']", "Bengaluru")
            page.select_option("select[name='language']", "english")
            page.select_option("select[name='state']", "Karnataka")
            page.wait_for_timeout(500)
            page.select_option("select[name='district']", "Bengaluru Urban")
            page.click("button[type='submit']")
            page.wait_for_load_state("networkidle")

        check_text(page, "h1", "Dashboard", exact=True)
        check_text(page, ".card-title", "Get Legal Advice")
        page.screenshot(path=f"{SCREENSHOT_DIR}/client_dashboard.png")

        # ---------- 3. LAWYER LOGIN + SETUP ----------
        print("\n=== 3. LAWYER LOGIN + SETUP ===")
        page.goto(f"{BASE_URL}/logout")
        page.goto(f"{BASE_URL}/lawyer/login")
        page.fill("input[name='phone']", "9990002222")
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")

        if "lawyer/setup" in page.url:
            page.fill("input[name='name']", "Test Lawyer")
            page.fill("input[name='email']", "testlawyer@example.com")
            page.fill("input[name='bar_council_id']", "BC12345")
            page.fill("input[name='enrolment_year']", "2015")
            page.select_option("select[name='experience_level']", "Senior")
            page.fill("input[name='consultation_fee']", "1500")
            page.fill("input[name='hearing_fee']", "6000")

            # Checkboxes for languages
            page.check("input[name='languages'][value='english']")
            page.check("input[name='languages'][value='kannada']")

            # Checkboxes for practice areas
            page.check("input[name='areas'][value='property']")
            page.check("input[name='areas'][value='family']")

            # Region first row
            page.select_option("select[name='region_state']", "Karnataka")
            page.wait_for_timeout(500)
            page.select_option("select[name='region_district']", "Bengaluru Urban")

            page.click("button[type='submit']")
            page.wait_for_load_state("networkidle")

        check_text(page, "h3", "Verification Pending")
        page.screenshot(path=f"{SCREENSHOT_DIR}/lawyer_pending.png")

        # ---------- 4. ADMIN LOGIN + DASHBOARD ----------
        print("\n=== 4. ADMIN LOGIN + DASHBOARD ===")
        page.goto(f"{BASE_URL}/lawyer/logout")
        page.goto(f"{BASE_URL}/admin/login")
        page.fill("input[name='phone']", "9999999999")
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")

        check_text(page, "h2", "Admin Dashboard")
        page.screenshot(path=f"{SCREENSHOT_DIR}/admin_dashboard.png")

        # ---------- 5. ADMIN VERIFIES LAWYER ----------
        print("\n=== 5. ADMIN VERIFIES LAWYER ===")
        page.goto(f"{BASE_URL}/admin/lawyers")
        page.wait_for_load_state("networkidle")
        page.click("a:has-text('Approve')")
        page.wait_for_load_state("networkidle")
        check_text(page, "td", "Test Lawyer")  # Lawyer name appears in table
        page.screenshot(path=f"{SCREENSHOT_DIR}/admin_lawyers.png")

        # ---------- 6. ADMIN CONTACT MANAGEMENT ----------
        print("\n=== 6. ADMIN CONTACT MANAGEMENT ===")
        page.goto(f"{BASE_URL}/admin/contact")
        page.fill("input[name='phone']", "1800-123-456")
        page.fill("input[name='email']", "support@nyayasetu.com")
        page.fill("textarea[name='address']", "123 Legal Street, Bengaluru")
        page.fill("input[name='working_hours']", "Mon-Fri 9AM-6PM")
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")
        check_text(page, "h5", "Contact Details")
        page.screenshot(path=f"{SCREENSHOT_DIR}/admin_contact.png")

        # ---------- 7. CLIENT CONTACT US ----------
        print("\n=== 7. CLIENT CONTACT US PAGE ===")
        page.goto(f"{BASE_URL}/logout")
        page.goto(f"{BASE_URL}/login")
        page.fill("input[name='phone']", "9990001111")
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")
        page.goto(f"{BASE_URL}/contact-us")
        check_text(page, "h3", "Contact Us")
        page.screenshot(path=f"{SCREENSHOT_DIR}/contact_us.png")

        print("\n🎉 All visual tests completed. Screenshots saved in 'tests/screenshots'.")
        browser.close()

if __name__ == "__main__":
    run_tests()
