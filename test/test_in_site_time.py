# -*- coding: utf-8 -*-
"""Find article links in chainthink.cn."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import requests
from bs4 import BeautifulSoup

url = "https://chainthink.cn/zh-CN/article"
r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
soup = BeautifulSoup(r.text, "html.parser")

# Check for data-* attributes that might contain article IDs
h3 = soup.find("h3")
print("=== H3 and its parent structure ===")
current = h3
for i in range(5):
    if not current:
        break
    print(f"{i}. <{current.name}> class={current.get('class', [])}")
    # Check for data attributes
    for attr, val in current.attrs.items():
        if attr.startswith("data-"):
            print(f"    {attr}={val}")
    current = current.find_parent()

# Look for any link-like patterns in the HTML
print("\n=== Looking for article link patterns ===")
# Check if there's a pattern like /zh-CN/article/xxx in hrefs
for a in soup.find_all("a", href=True)[:20]:
    href = a.get("href", "")
    if "/article/" in href or "/zh-CN/article" in href:
        print(f"Found link: {href[:80]}")

# Check for cursor-pointer divs (might be clickable)
print("\n=== Looking for clickable divs ===")
for div in soup.find_all("div", class_="cursor-pointer")[:3]:
    print(f"Div class: {div.get('class', [])}")
    # Check for data attributes
    for attr, val in div.attrs.items():
        if attr.startswith("data-"):
            print(f"  {attr}={val}")
    # Look for h3 inside
    h3 = div.find("h3")
    if h3:
        print(f"  Contains h3: {h3.get_text(strip=True)[:40]}")
