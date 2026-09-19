name: Generate Recipe A4

on:
  workflow_dispatch:
    inputs:
      recipe_url:
        description: 'Link do przepisu kulinarnego'
        required: true
        type: string

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install requests

      - name: Run Generator Script
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          RECIPE_URL: ${{ github.event.inputs.recipe_url }}
        run: python scripts/generate_recipe.py

      - name: Commit and Push changes
        run: |
          git config --global user.name 'GitHub Action'
          git config --global user.email 'action@github.com'
          git add przepisy/ recipes.json
          git status
          git diff-index --quiet HEAD || git commit -m "Dodano nowy przepis z URL: ${{ github.event.inputs.recipe_url }}"
          git push
