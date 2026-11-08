import os
import re
import json
import base64
import requests
from datetime import datetime

MODEL_NAME = "gemini-3.8-flash"

PAID_KEY = os.environ.get("GEMINI_API_KEY")
FREE_KEY = os.environ.get("GEMINI_API_KEY_DARMOWY")
API_KEY_TYPE = os.environ.get("API_KEY_TYPE", "paid")

if API_KEY_TYPE == "free":
    GEMINI_API_KEY = FREE_KEY
    print("Używam darmowego klucza API (GEMINI_API_KEY_DARMOWY)")
else:
    GEMINI_API_KEY = PAID_KEY
    print("Używam płatnego klucza API (GEMINI_API_KEY)")

INPUT_TYPE = os.environ.get("INPUT_TYPE", "url")
RECIPE_INPUT = os.environ.get("RECIPE_INPUT")
CUSTOM_TITLE = os.environ.get("CUSTOM_TITLE", "").strip()

if not GEMINI_API_KEY or not RECIPE_INPUT:
    raise ValueError(f"Brak wybranego klucza API (typ: {API_KEY_TYPE}) lub danych wejściowych!")

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

prompt_base = """Przeanalizuj dostarczone materiały (link lub jedno/dwa zdjęcia kolejnych stron przepisu) i wygeneruj KOMPLETNY, SAMOWYSTARCZALNY kod pliku HTML dla strony książki kucharskiej.

Najważniejsze zasady:
1. **Wierne odwzorowanie**: Nie zmieniaj, nie modyfikuj ani nie ulepszaj przepisu. Przepis (składniki, proporcje, kroki przygotowania) ma być **wierną kopią** tego, co znajduje się w dostarczonych materiałach. Jeśli przepis rozpisany jest na dwóch stronach/zdjęciach, połącz je w jedną spójną całość.
2. **Brak zdjęć**: Nie dodawaj żadnych zdjęć ani grafik potrawy. Strona ma zawierać **wyłącznie czysty tekst**, sformatowany w czytelny sposób.
3. **Responsywność mobilna i A4**: Strona musi wyglądać świetnie na telefonach oraz idealnie mieścić się na **jednej stronie A4** po wydrukowaniu. Użyj stylów CSS: `@page { size: A4 portrait; margin: 10mm; }`.
4. **Bezpieczne szerokości**: Używaj elastycznych kontenerów (`max-width: 100%`, `box-sizing: border-box`). Teksty i listy składników muszą się zawijać i nigdy nie wychodzić poza ekran telefonu.
5. Styl ma przypominać elegancką, tradycyjną książkę kucharską (estetyczne ramki, klasyczne czcionki serif, wyraźny podział na składniki i przygotowanie krok po kroku).
6. **Koniecznie dodaj na samej górze kodu HTML (w sekcji <head> oraz w <body>) następujący styl i widget z przyciskiem drukowania i powrotu:**
   - W sekcji <style> dodaj: `@media print { .no-print { display: none; } }`
   - W sekcji <body> (jako pierwszy element) dodaj pływający panel:
     <div class="no-print" style="position: fixed; top: 10px; right: 10px; background: #fff; padding: 10px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.2); z-index: 9999;">
       <button onclick="window.print()" style="background: #8b5e3c; color: #fff; border: none; padding: 8px 12px; border-radius: 4px; cursor: pointer; font-weight: bold;">🖨️ Drukuj / Zapisz PDF</button>
       <a href="../index.html" style="margin-left: 10px; color: #8b5e3c; text-decoration: none; font-weight: bold;">← Powrót</a>
     </div>
7. ZWRÓĆ WYŁĄCZNIE CZYSTY KOD HTML, bez znaczników ```html na początku ani końcu. Kod musi zaczynać się od <!DOCTYPE html>.
8. Pierwszy znacznik <h1> musi zawierać pełny, dokładny tytuł przepisu."""

if CUSTOM_TITLE:
    prompt_base += f"\n9. **WAŻNE**: Główne nagłówek H1 na tej stronie HTML MUSI brzmieć dokładnie: '{CUSTOM_TITLE}'."

contents_payload = [{"text": prompt_base}]

if INPUT_TYPE == "image":
    image_parts = RECIPE_INPUT.split("|||")
    for img_data in image_parts:
        if not img_data.strip():
            continue
        header, encoded = img_data.split(",", 1)
        mime_type = header.split(";")[0].replace("data:", "")
        contents_payload.append({
            "inline_data": {
                "mime_type": mime_type,
                "data": encoded
            }
        })
else:
    contents_payload[0]["text"] = f"{prompt_base}\n\nLink do przepisu: {RECIPE_INPUT}"

domain = "generativelanguage.googleapis.com"
endpoint = f"/v1beta/models/{MODEL_NAME}:generateContent"
url = f"https://{domain}{endpoint}?key={GEMINI_API_KEY}"

payload = {
    "contents": [{"parts": contents_payload}],
    "tools": []
}

response = requests.post(url, json=payload)
if not response.ok:
    raise RuntimeError(f"Błąd API Gemini ({response.status_code}): {response.text}")

res_data = response.json()
html_code = res_data["candidates"][0]["content"]["parts"][0]["text"]
html_code = re.sub(r'^```html\s*', '', html_code, flags=re.I)
html_code = re.sub(r'```\s*$', '', html_code).strip()

if CUSTOM_TITLE:
    recipe_title = CUSTOM_TITLE
else:
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

print(f"Pomyślnie wygenerowano przepis: '{recipe_title}' w pliku {html_file_path}")
