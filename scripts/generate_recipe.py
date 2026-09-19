import os
import re
import json
import requests
from datetime import datetime

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
RECIPE_URL = os.environ.get("RECIPE_URL")

if not GEMINI_API_KEY or not RECIPE_URL:
    raise ValueError("Brak wymaganego GEMINI_API_KEY lub RECIPE_URL!")

def slugify(text):
    text = text.lower().strip()
    replacements = {
        'ł': 'l', 'ą': 'a', 'ę': 'e', 'ć': 'c', 'ń': 'n',
        'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z'
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    text = re.sub(r'\s+', '-', text)
    text = re.sub(r'[^\w\-]+', '', text)
    return re.sub(r'\-\-+', '-', text)

prompt_text = f"""Pobierz i przeanalizuj przepis ze strony: {RECIPE_URL}.
Wygeneruj KOMPLETNY, SAMOWYSTARCZALNY kod pliku HTML.
Wymagania:
1. Kieruj się promptem użytkownika: "Przygotuj mi przepis do wydrukowania na jednej kartce a4, dodaj zdjęcie aby kartka wyglądała jak z książki kucharskiej, przygotuj pdf".
2. Strona musi zawierać dedykowane style CSS do druku (@page {{ size: A4 portrait; margin: 10mm; }}), tak aby po otwarciu i wybraniu Druku (Ctrl+P / Zapisz jako PDF) cały przepis mieścił się idealnie na JEDNEJ stronie A4.
3. Styl ma przypominać elegancką stronę z tradycyjnej książki kucharskiej (ładne nagłówki, estetyczne marginesy, czytelne składniki, krok po kroku).
4. Dołącz ładne zdjęcie potrawy (znajdź pasujący link lub z oryginalnej strony).
5. ZWRÓĆ WYŁĄCZNIE CZYSTY KOD HTML, bez zbędnych komentarzy czy znaczników typu ```html na początku/końcu. Kod powinieneś zacząć od <!DOCTYPE html>.
6. Pierwszy znacznik <h1> powinien zawierać pełny tytuł przepisu."""

url = f"[https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=](https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=){GEMINI_API_KEY}"
payload = {
    "contents": [{"parts": [{"text": prompt_text}]}],
    "tools": [{"google_search": {}}]
}

response = requests.post(url, json=payload)
response.raise_for_status()

res_data = response.json()
html_code = res_data["candidates"][0]["content"]["parts"][0]["text"]
html_code = re.sub(r'^```html\s*', '', html_code, flags=re.I)
html_code = re.sub(r'```\s*$', '', html_code).strip()

title_match = re.search(r'<h1[^>]*>(.*?)</h1>', html_code, re.I | re.S)
if title_match:
    recipe_title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
else:
    recipe_title = "Nowy Przepis"

file_slug = slugify(recipe_title) or f"przepis-{int(datetime.now().timestamp())}"
os.makedirs("przepisy", exist_ok=True)
html_file_path = f"przepisy/{file_slug}.html"

with open(html_file_path, "w", encoding="utf-8") as f:
    f.write(html_code)

recipes_file = "recipes.json"
recipes = []
if os.path.exists(recipes_file):
    try:
        with open(recipes_file, "r", encoding="utf-8") as f:
            recipes = json.load(f)
    except Exception:
        recipes = []

new_entry = {
    "id": file_slug,
    "title": recipe_title,
    "file": html_file_path,
    "date": datetime.now().strftime("%Y-%m-%d")
}

recipes.insert(0, new_entry)

with open(recipes_file, "w", encoding="utf-8") as f:
    json.dump(recipes, f, ensure_ascii=False, indent=2)

print(f"Pomyślnie wygenerowano przepis: {recipe_title} ({html_file_path})")
