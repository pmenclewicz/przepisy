import os
import re
import json
import requests
from datetime import datetime

# ==============================================================================
# KONFIGURACJA I ZMIENNE WEJŚCIOWE (GitHub Models)
# ==============================================================================
MODEL_NAME = "gpt-4o-mini"

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
RECIPE_URL = os.environ.get("RECIPE_URL")

if not GITHUB_TOKEN or not RECIPE_URL:
    raise ValueError("Brak wymaganego GITHUB_TOKEN lub RECIPE_URL w zmiennych środowiskowych!")


def slugify(text):
    """Przekształca tekst na przyjazny dla URL-i i nazw plików format."""
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


# ==============================================================================
# ZAPYTANIE DO GITHUB MODELS API
# ==============================================================================
prompt_text = f"""Przeanalizuj przepis z podanego linku: {RECIPE_URL}.
Wygeneruj KOMPLETNY, SAMOWYSTARCZALNY kod pliku HTML.

Wymagania:
1. Przepis przeznaczony do wydruku na JEDNEJ kartce A4.
2. Strona musi zawierać dedykowane style CSS do druku (@page {{ size: A4 portrait; margin: 10mm; }}), tak aby po otwarciu i wybraniu Druku (Ctrl+P / Zapisz jako PDF) cały przepis mieścił się idealnie na JEDNEJ stronie A4.
3. Styl ma przypominać elegancką stronę z tradycyjnej książki kucharskiej (ładne nagłówki, estetyczne marginesy, czytelne składniki, krok po kroku).
4. Dołącz ładne zdjęcie potrawy (użyj pasującego zdjęcia z Unsplash dla tej potrawy).
5. ZWRÓĆ WYŁĄCZNIE CZYSTY KOD HTML, bez zbędnych komentarzy czy znaczników typu ```html na początku/końcu. Kod powinieneś zacząć od <!DOCTYPE html>.
6. Pierwszy znacznik <h1> powinien zawierać pełny tytuł przepisu."""

# Bezpieczne budowanie adresu URL (wyklucza błąd InvalidSchema z nawiasami)
scheme = "https://"
domain = "models.inference.ai.azure.com"
path = "/chat/completions"
api_url = f"{scheme}{domain}{path}"

headers = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Content-Type": "application/json"
}

payload = {
    "messages": [
        {
            "role": "system",
            "content": "Jesteś profesjonalnym szefem kuchni oraz ekspertem web deweloperem. Generujesz wyłącznie gotowy, czysty kod HTML."
        },
        {
            "role": "user",
            "content": prompt_text
        }
    ],
    "model": MODEL_NAME,
    "temperature": 0.5
}

print(f"Wysyłanie zapytania do GitHub Models API (Model: {MODEL_NAME})...")
response = requests.post(api_url, headers=headers, json=payload)
response.raise_for_status()

res_data = response.json()

# Wyciągnięcie kodu HTML z odpowiedzi OpenAI/GitHub API
html_code = res_data["choices"][0]["message"]["content"]
html_code = re.sub(r'^```html\s*', '', html_code, flags=re.I)
html_code = re.sub(r'```\s*$', '', html_code).strip()

# Wydobycie tytułu z pierwszego nagłówka <h1>
title_match = re.search(r'<h1[^>]*>(.*?)</h1>', html_code, re.I | re.S)
if title_match:
    recipe_title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
else:
    recipe_title = "Nowy Przepis"

# ==============================================================================
# ZAPIS PLIKU HTML I AKTUALIZACJA BAZY RECIPES.JSON
# ==============================================================================
file_slug = slugify(recipe_title) or f"przepis-{int(datetime.now().timestamp())}"
os.makedirs("przepisy", exist_ok=True)
html_file_path = f"przepisy/{file_slug}.html"

# Zapis pliku przepisu
with open(html_file_path, "w", encoding="utf-8") as f:
    f.write(html_code)

# Aktualizacja pliku recipes.json
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

print(f"Pomyślnie wygenerowano przepis: '{recipe_title}' w pliku {html_file_path}")
