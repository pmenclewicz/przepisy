import os
import re
import json
import base64
import requests
from datetime import datetime

API_KEY_TYPE = os.environ.get("API_KEY_TYPE", "paid")
INPUT_TYPE = os.environ.get("INPUT_TYPE", "url")
RECIPE_INPUT = os.environ.get("RECIPE_INPUT")
CUSTOM_TITLE = os.environ.get("CUSTOM_TITLE", "").strip()

if not RECIPE_INPUT:
    raise ValueError("Brak danych wejściowych z przepisem!")

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

html_code = ""

# LOGIKA DLA MODELU GROQ
if API_KEY_TYPE == "groq":
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
    if not GROQ_API_KEY:
        raise ValueError("Brak klucza GROQ_API_KEY w secretach repozytorium!")
    
    print("Używam darmowego API Groq (qwen/qwen3.8-27b)")
    
    messages_content = []
    
    if INPUT_TYPE == "image":
        messages_content.append({"type": "text", "text": prompt_base})
        image_parts = RECIPE_INPUT.split("|||")
        for img_data in image_parts:
            if img_data.strip():
                messages_content.append({
                    "type": "image_url",
                    "image_url": {"url": img_data}
                })
    else:
        full_text = f"{prompt_base}\n\nLink do przepisu: {RECIPE_INPUT}"
        messages_content.append({"type": "text", "text": full_text})

    payload = {
        "model": "qwen/qwen3.8-27b",
        "messages": [{"role": "user", "content": messages_content}],
        "temperature": 0.2
    }
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    groq_url = "https://" + "api.groq.com" + "/openai/v1/chat/completions"
    response = requests.post(groq_url, json=payload, headers=headers)
    if not response.ok:
        raise RuntimeError(f"Błąd API Groq ({response.status_code}): {response.text}")
    
    res_data = response.json()
    html_code = res_data["choices"][0]["message"]["content"]

# LOGIKA DLA MODELI GEMINI (PAID / FREE)
else:
    if API_KEY_TYPE == "free":
        GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY_DARMOWY")
        print("Używam darmowego klucza API (GEMINI_API_KEY_DARMOWY)")
    else:
        GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
        print("Używam płatnego klucza API (GEMINI_API_KEY)")

    if not GEMINI_API_KEY:
        raise ValueError(f"Brak klucza API dla wybranego typu Gemini ({API_KEY_TYPE})!")

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

    MODEL_NAME = "gemini-3.8-flash"
    gemini_url = "https://" + "generativelanguage.googleapis.com" + f"/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"

    payload = {"contents": [{"parts": contents_payload}]}
    response = requests.post(gemini_url, json=payload)
    
    if not response.ok:
        raise RuntimeError(f"Błąd API Gemini ({response.status_code}): {response.text}")

    res_data = response.json()
    
    # BEZPIECZNE POBIERANIE TREŚCI Z GEMINI (OBSŁUGA FILTRÓW BEZPIECZEŃSTWA / BŁĘDÓW)
    try:
        html_code = res_data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Gemini nie zwróciło poprawnej treści (prawdopodobnie blokada bezpieczeństwa lub pusta odpowiedź). Pełny komunikat API: {json.dumps(res_data, ensure_ascii=False)}")

# CZYSZCZENIE OTRZYMANEGO HTML
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

# AKTUALIZACJA RECIPES.JSON
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
