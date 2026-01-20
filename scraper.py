#!/usr/bin/env python3
"""
Treefort Systems Group Memberships Scraper
Logs into the admin panel and exports group membership data to CSV
"""

import csv
import os
import getpass
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


# Configuration
LOGIN_URL = "https://admin.treefortsystems.com"
TARGET_URL = "https://admin.treefortsystems.com/monetization/group-memberships"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "exports")

# Create exports folder if it doesn't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)


def scrape_group_memberships():
    """Main scraper function"""

    # Prompt for credentials
    print("=== Treefort Group Memberships Scraper ===\n")
    username = input("Enter username (email): ")
    password = getpass.getpass("Enter password: ")
    print()

    with sync_playwright() as p:
        # Launch browser (headless=True for background execution)
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        print("Navigating to login page...")
        page.goto(LOGIN_URL, wait_until="networkidle")

        # Wait for the page to load and find login form
        print("Logging in...")

        # Try to find and fill login fields - adjust selectors as needed
        try:
            # Common login field selectors - will try multiple approaches
            # Try email/username field
            email_selectors = [
                'input[type="email"]',
                'input[name="email"]',
                'input[name="username"]',
                'input[placeholder*="email" i]',
                'input[placeholder*="username" i]',
                '#email',
                '#username'
            ]

            password_selectors = [
                'input[type="password"]',
                'input[name="password"]',
                '#password'
            ]

            # Find and fill email field
            email_filled = False
            for selector in email_selectors:
                try:
                    if page.locator(selector).count() > 0:
                        page.fill(selector, username)
                        email_filled = True
                        print(f"  Filled email using: {selector}")
                        break
                except:
                    continue

            if not email_filled:
                print("  Could not find email field, trying to click visible inputs...")
                inputs = page.locator('input:visible')
                if inputs.count() >= 2:
                    inputs.nth(0).fill(USERNAME)
                    email_filled = True

            # Find and fill password field
            password_filled = False
            for selector in password_selectors:
                try:
                    if page.locator(selector).count() > 0:
                        page.fill(selector, password)
                        password_filled = True
                        print(f"  Filled password using: {selector}")
                        break
                except:
                    continue

            # Click login/submit button
            submit_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Log in")',
                'button:has-text("Login")',
                'button:has-text("Sign in")',
                'button:has-text("Submit")'
            ]

            for selector in submit_selectors:
                try:
                    if page.locator(selector).count() > 0:
                        page.click(selector)
                        print(f"  Clicked submit using: {selector}")
                        break
                except:
                    continue

            # Wait for navigation after login
            page.wait_for_load_state("networkidle", timeout=15000)
            print("  Login submitted, waiting for redirect...")

        except Exception as e:
            print(f"Login error: {e}")
            # Take screenshot for debugging
            page.screenshot(path=os.path.join(OUTPUT_DIR, "login_error.png"))
            browser.close()
            return

        # Navigate to group memberships page
        print(f"Navigating to group memberships: {TARGET_URL}")
        page.goto(TARGET_URL, wait_until="networkidle")
        page.wait_for_timeout(2000)  # Extra wait for dynamic content

        # Try to find and click "Group Memberships" tab if needed
        try:
            tab_selectors = [
                'a:has-text("Group Memberships")',
                'button:has-text("Group Memberships")',
                '[role="tab"]:has-text("Group Memberships")',
                'nav a:has-text("Group")'
            ]
            for selector in tab_selectors:
                if page.locator(selector).count() > 0:
                    page.click(selector)
                    print(f"  Clicked tab: {selector}")
                    page.wait_for_load_state("networkidle")
                    break
        except:
            pass  # Tab might already be selected or not exist

        page.wait_for_timeout(2000)

        # Extract table data
        print("Extracting table data...")

        # First, try to load all data (handle pagination if exists)
        try:
            # Look for "show all" or pagination controls
            show_all_selectors = [
                'select option:has-text("All")',
                'button:has-text("Show all")',
                'a:has-text("Show all")',
                '[data-testid="rows-per-page"]'
            ]
            for selector in show_all_selectors:
                if page.locator(selector).count() > 0:
                    page.click(selector)
                    page.wait_for_load_state("networkidle")
                    break
        except:
            pass

        # Extract headers
        headers = []
        header_selectors = ['table thead th', 'table th', '[role="columnheader"]', '.header-cell']

        for selector in header_selectors:
            header_elements = page.locator(selector)
            if header_elements.count() > 0:
                for i in range(header_elements.count()):
                    text = header_elements.nth(i).inner_text().strip()
                    if text:
                        headers.append(text)
                if headers:
                    print(f"  Found {len(headers)} headers: {headers}")
                    break

        if not headers:
            print("  No table headers found, trying to extract from first row...")
            # Take screenshot for debugging
            page.screenshot(path=os.path.join(OUTPUT_DIR, "page_state.png"))

        # Extract rows
        rows_data = []
        row_selectors = ['table tbody tr', 'table tr:not(:first-child)', '[role="row"]']

        for selector in row_selectors:
            row_elements = page.locator(selector)
            row_count = row_elements.count()

            if row_count > 0:
                print(f"  Found {row_count} rows using: {selector}")

                for i in range(row_count):
                    row = row_elements.nth(i)
                    cells = row.locator('td, [role="cell"]')
                    cell_count = cells.count()

                    if cell_count > 0:
                        row_data = []
                        for j in range(cell_count):
                            cell_text = cells.nth(j).inner_text().strip()
                            row_data.append(cell_text)

                        if row_data and any(row_data):  # Skip empty rows
                            rows_data.append(row_data)

                if rows_data:
                    break

        print(f"  Extracted {len(rows_data)} data rows")

        # If no headers found but we have data, use generic headers
        if not headers and rows_data:
            headers = [f"Column_{i+1}" for i in range(len(rows_data[0]))]

        # Split "Members" column into "Active Members" and "Possible Members"
        if "Members" in headers:
            members_idx = headers.index("Members")
            # Update headers
            headers = headers[:members_idx] + ["Active Members", "Possible Members"] + headers[members_idx + 1:]

            # Update each row
            for i, row in enumerate(rows_data):
                if members_idx < len(row):
                    members_value = row[members_idx]
                    # Parse the fraction (e.g., "3/5" or "5/5\nFull")
                    members_clean = members_value.split('\n')[0].strip()  # Remove "Full" text if present
                    if '/' in members_clean:
                        parts = members_clean.split('/')
                        active = parts[0].strip()
                        possible = parts[1].strip()
                    else:
                        active = members_clean
                        possible = ""
                    # Replace the row with split values
                    rows_data[i] = row[:members_idx] + [active, possible] + row[members_idx + 1:]

            print(f"  Split 'Members' column into 'Active Members' and 'Possible Members'")

        # Export to CSV
        if headers or rows_data:
            current_date = datetime.now().strftime("%Y-%m-%d")
            csv_filename = f"{current_date}.csv"
            csv_path = os.path.join(OUTPUT_DIR, csv_filename)

            print(f"Exporting to CSV: {csv_path}")

            with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)

                if headers:
                    writer.writerow(headers)

                for row in rows_data:
                    writer.writerow(row)

            print(f"Successfully exported {len(rows_data)} rows to {csv_filename}")
        else:
            print("No data found to export!")
            # Save screenshot for debugging
            page.screenshot(path=os.path.join(OUTPUT_DIR, "no_data_found.png"))

            # Also save the page HTML for debugging
            html_content = page.content()
            with open(os.path.join(OUTPUT_DIR, "page_debug.html"), 'w') as f:
                f.write(html_content)
            print("Saved debug screenshot and HTML to Desktop")

        # Close browser
        browser.close()
        print("Done!")


if __name__ == "__main__":
    scrape_group_memberships()
