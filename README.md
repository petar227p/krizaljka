# Križaljka

A personal crossword player for the 24sata daily puzzles. Not for publishing.

## Files

- `fetch_krizaljka.py`: downloads puzzles and saves them to `data/`
- `data/<date>.json`: one clean JSON file per puzzle
- `data/puzzles.js`, `data/index.json`: generated from the JSON files for the page
- `index.html`: the player. Open it in a browser (double-click works).

## Usage

Catch up: fetch every day after the newest saved puzzle, through today:

```bash
python3 fetch_krizaljka.py
```

If you skipped a few days, one run fills in all of them. If you're up to date, it says so and does nothing.

Download a range (dates in either order):

```bash
python3 fetch_krizaljka.py 2026-09-01 2026-10-08
```

Days already in `data/` are skipped. Requires Python 3 only, no packages.

”# krizaljka”
