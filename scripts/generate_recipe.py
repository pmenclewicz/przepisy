import os
import re
import json
import base64
import requests
from datetime import datetime

MODEL_NAME = "gemini-3.6-flash"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
INPUT_TYPE = os.environ.get("INPUT_TYPE", "url")
RECIPE_INPUT = os.environ.get("RECIPE_INPUT")

if not GEMINI_API_KEY or not RECIPE_INPUT:
    raise ValueError("Brak wymaganych zmiennych środowiskowych GEMINI_API_KEY lub RECIPE_INPUT!")

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
    return re.sub(r'\-+', '-', text)

prompt_base = """Przeanalizuj dostarczone materiały (link lub zdjęcie przepisu) i wygeneruj KOMPLETNY, SAMOWYSTARCZALNY kod pliku HTML dla strony książki kucharskiej.
Wymagania:
1. Strona ma być zaprojektowana tak, aby idealnie mieściła się na **jednej stronie A4** po wydrukowaniu (użyj dedykovanych stylów CSS: @page { size: A4 portrait; margin: 10mm; }).
2. Styl ma przypominać elegancką, tradycyjną książkę kucharską (estetyczne ramki, klasyczne czcionki serif, wyraźny podział na składniki i przygotowanie krok po kroku).
3. Dołącz ładne zdjęcie potrawy (jeśli pochodzi z linku lub ze zdjęcia, wykorzystaj pasujący link graficzny lub zdekodowane zdjęcie).
4. **Koniecznie dodaj na samej górze kodu HTML (w sekcji <head> oraz w <body>) następujący styl i widget z przyciskiem drukowania i powrotu:**
   - W sekcji <style> dodaj: `@media print { .no-print { display: none; } }`
   - W sekcji <body> (jako pierwszy element) dodaj pływający panel:
     <div class="no-print" style="position: fixed; top: 10px; right: 10px; background: #fff; padding: 10px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.2); z-index: 9999;">
       <button onclick="window.print()" style="background: #8b5e3c; color: #fff; border: none; padding: 8px 12px; border-radius: 4px; cursor: pointer; font-weight: bold;">🖨️ Drukuj / Zapisz PDF</button>
       <a href="../index.html" style="margin-left: 10px; color: #8b5e3c; text-decoration: none; font-weight: bold;">← Powrót</a>
     </div>
5. ZWRÓĆ WYŁĄCZNIE CZYSTY KOD HTML, bez znaczników ```html na początku ani końcu. Kod musi zaczynać się od <!DOCTYPE html>.
6. Pierwszy znacznik <h1> musi zawierać pełny, dokładny tytuł przepisu."""

contents_payload = []

if INPUT_TYPE == "image":
    header, encoded = RECIPE_INPUT.split(",", 1)
    mime_type = header.split(";")[0].replace("data:", "")
    
    contents_payload = [
        {"text": prompt_base},
        {
            "inline_data": {
                "mime_type": mime_type,
                "data": encoded
            }
        }
    ]
else:
    prompt_text = f"{prompt_base}\n\nLink do przepisu: {RECIPE_INPUT}"
    contents_payload = [{"text": prompt_text}]

domain = "generativelanguage.googleapis.com"
endpoint = f"/v1beta/models/{MODEL_NAME}:generateContent"
url = f"https://{domain}{endpoint}?key={GEMINI_API_KEY}"

payload = {
    "contents": [{"parts": contents_payload}],
    "tools": [{"google_search": {}}] if INPUT_TYPE == "url" else []
}

response = requests.post(url, json=payload)
if not response.ok:
    raise RuntimeError(f"Błąd API Gemini ({response.status_code}): {response.text}")

res_data = response.json()
html_code = res_data["candidates"][0]["content"]["parts"][0]["text"]
html_code = re.sub(r'^```html\s*', '', html_code, flags=re.I)
html_code = re.sub(r'```\s*$', '', html_code).strip()

title_match = re.search(r'<h1[^>]*>(.*?)</h1>', html_code, re.I | re.S)
recipe_title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else "Nowy Przepis"

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

recipes = [r for r in recipes if r["id"] != file_slug]
recipes.insert(0, new_entry)

with open(recipes_file, "w", encoding="utf-8") as f:
    json.dump(recipes, f, ensure_ascii=False, indent=2)

print(f"Pomyślnie wygenerowano przepis: '{recipe_title}' in {html_file_path}")
