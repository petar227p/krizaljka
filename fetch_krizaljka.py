#!/usr/bin/env python3
"""Download 24sata krizaljke (crosswords) and save them as clean JSON.

Usage:
    python3 fetch_krizaljka.py                       # catch up: every day after the newest saved one, through today
    python3 fetch_krizaljka.py 2026-10-08            # one day
    python3 fetch_krizaljka.py 2026-09-01 2026-10-08 # a date range (inclusive)

Files are written to data/<date>.json. Days already on disk are skipped,
so you can re-run the script safely.
"""

import base64
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse

# The same endpoint the 24sata page calls from its embedded iframe.
ENDPOINT = "https://enigma.kreda.hr/crosswords.php"
REFERER = "https://www.24sata.hr/"
USER_AGENT = "Mozilla/5.0 (personal crossword project)"

DATA_DIR = Path(__file__).parent / "data"
IMAGES_DIR = DATA_DIR / "images"
DELAY_SECONDS = 1.0  # be polite; one request per second


def fetch_raw(day: str) -> dict:
    """POST to the endpoint and return the decoded JSON payload."""
    body = urllib.parse.urlencode({"date": day, "client": 1, "layout": "desktop"}).encode()
    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        headers={"Referer": REFERER, "User-Agent": USER_AGENT},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        encoded = resp.read().decode("ascii").strip()

    # The response is base64 of a URL-encoded UTF-8 JSON string.
    text = urllib.parse.unquote(base64.b64decode(encoded).decode("utf-8"))
    return json.loads(text)


def normalize(day: str, raw: dict) -> dict:
    """Turn the 24sata layout into a simple grid + list of clues.

    In the raw data, questions[row][col] is one of:
      - missing          -> black square
      - {"type": ...}    -> letter cell ("answer-special") or the arrow
      - {"h": {...}}     -> clue cell for a word going right (the word starts to its right)
      - {"v": {...}}     -> clue cell for a word going down (the word starts below it)
    Each clue has "q" (question) and "a" (answer, may contain spaces).
    """
    width = int(raw["options"]["sizeW"])
    height = int(raw["options"]["sizeH"])
    questions = raw["questions"]
    # Letters that occupy one square even though they are two characters (DŽ, LJ, NJ).
    digraphs = [v for v in raw["options"]["allowChars"].values() if len(v) > 1]

    # solution[y][x] is "#" for black squares and the answer letter otherwise.
    # letter_cell[y][x] says whether the player types into that square.
    solution = [["#" for _ in range(width)] for _ in range(height)]
    letter_cell = [[False] * width for _ in range(height)]
    clue_cell = [[False] * width for _ in range(height)]
    clues = {"across": [], "down": []}

    for y_str, row in questions.items():
        y = int(y_str)
        for x_str, cell in row.items():
            x = int(x_str)
            if not isinstance(cell, dict):
                continue
            if "h" in cell or "v" in cell:
                clue_cell[y][x] = True
            if "h" in cell:
                clues["across"].append(_clue(cell["h"], y, x + 1, "across", digraphs))
            if "v" in cell:
                clues["down"].append(_clue(cell["v"], y + 1, x, "down", digraphs))

    # Work out which squares are letters by walking every word.
    for clue_list, step in ((clues["across"], (0, 1)), (clues["down"], (1, 0))):
        for clue in clue_list:
            r, c = clue["row"], clue["col"]
            for i, letter in enumerate(clue["tokens"]):
                rr, cc = r + step[0] * i, c + step[1] * i
                letter_cell[rr][cc] = True
                solution[rr][cc] = letter

    # Crossing squares must agree; if they don't, the data (or our reading of it) is off.
    conflicts = _check_crossings(clues, width, height)

    # Number the clues in reading order, the way a printed puzzle does.
    _number_clues(clues)

    return {
        "date": day,
        "id": raw.get("id"),
        "title": raw.get("title"),
        "width": width,
        "height": height,
        "grid": [
            [
                {"letter": solution[y][x], "kind": _kind(letter_cell[y][x], clue_cell[y][x])}
                for x in range(width)
            ]
            for y in range(height)
        ],
        "clues": clues,
        "warnings": conflicts,
    }


def attach_images(day: str, raw: dict, puzzle: dict) -> None:
    """Download each picture and record which rectangle of the grid it covers.

    The picture sits over black squares. The page places it with CSS grid
    using the start/end coordinates, so it scales with the board.
    """
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    puzzle["images"] = []
    for n, im in sorted(raw.get("images", {}).items(), key=lambda kv: int(kv[0])):
        entry = {
            "startX": int(im["startX"]), "startY": int(im["startY"]),
            "endX": int(im["endX"]), "endY": int(im["endY"]),
            "file": None,
        }
        # Warn if the picture would cover letters or clues instead of black squares.
        for y in range(entry["startY"], entry["endY"] + 1):
            for x in range(entry["startX"], entry["endX"] + 1):
                if puzzle["grid"][y][x]["kind"] != "black":
                    puzzle["warnings"].append(f"image {n} covers a non-black square at row {y}, col {x}")

        url = im["src"]
        if url.startswith("//"):
            url = "https:" + url
        ext = Path(urlparse(url).path).suffix or ".jpg"
        dest = IMAGES_DIR / f"{day}-{n}{ext}"
        try:
            req = urllib.request.Request(url, headers={"Referer": REFERER, "User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=20) as resp:
                dest.write_bytes(resp.read())
            entry["file"] = f"data/images/{dest.name}"  # relative to the project folder
        except Exception as exc:  # a missing picture should not lose the whole puzzle
            puzzle["warnings"].append(f"image {n} not downloaded ({exc})")
        puzzle["images"].append(entry)


def _kind(is_letter: bool, is_clue: bool) -> str:
    """'letter' = type here, 'clue' = shows a clue, 'black' = empty square."""
    if is_letter:
        return "letter"
    if is_clue:
        return "clue"
    return "black"


def _clue(entry: dict, row: int, col: int, direction: str, digraphs: list) -> dict:
    answer_raw = entry.get("a", "")
    letters = answer_raw.replace(" ", "")
    return {
        "row": row,
        "col": col,
        "direction": direction,
        "clue": entry.get("q", ""),
        "answer": letters,
        "answerRaw": answer_raw,
        "tokens": _tokenize(letters, digraphs),
    }


def _tokenize(text: str, digraphs: list) -> list:
    """Split an answer into squares: 'ADŽ' -> ['A', 'DŽ'] when DŽ is one square."""
    tokens = []
    i = 0
    while i < len(text):
        for dg in sorted(digraphs, key=len, reverse=True):
            if text.startswith(dg, i):
                tokens.append(dg)
                i += len(dg)
                break
        else:
            tokens.append(text[i])
            i += 1
    return tokens


def _check_crossings(clues: dict, width: int, height: int) -> list:
    """Return a list of human-readable problems, empty when everything lines up."""
    seen = {}
    problems = []
    for clue in clues["across"] + clues["down"]:
        step = (0, 1) if clue["direction"] == "across" else (1, 0)
        for i, letter in enumerate(clue["tokens"]):
            r = clue["row"] + step[0] * i
            c = clue["col"] + step[1] * i
            if not (0 <= r < height and 0 <= c < width):
                problems.append(f"{clue['direction']} word out of bounds: {clue['answerRaw']}")
                break
            if (r, c) in seen and seen[(r, c)] != letter:
                problems.append(f"crossing mismatch at row {r}, col {c}")
            seen[(r, c)] = letter
    return problems


def _number_clues(clues: dict) -> None:
    """Give each clue a number based on its start square, reading order (like print)."""
    starts = sorted({(c["row"], c["col"]) for c in clues["across"] + clues["down"]})
    number_for = {pos: i + 1 for i, pos in enumerate(starts)}
    for clue in clues["across"] + clues["down"]:
        clue["number"] = number_for[(clue["row"], clue["col"])]


def save(day: str, puzzle: dict) -> Path:
    DATA_DIR.mkdir(exist_ok=True)
    path = DATA_DIR / f"{day}.json"
    path.write_text(json.dumps(puzzle, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def update_index() -> None:
    """Write data/index.json and data/puzzles.js for every saved day, newest first.

    puzzles.js exists so the HTML page can load the data with a plain <script> tag,
    which works when you double-click index.html (no web server needed).
    """
    DATA_DIR.mkdir(exist_ok=True)
    days = sorted((p.stem for p in DATA_DIR.glob("*.json") if p.stem not in ("index",)), reverse=True)
    (DATA_DIR / "index.json").write_text(json.dumps(days, indent=2), encoding="utf-8")

    puzzles = {d: json.loads((DATA_DIR / f"{d}.json").read_text(encoding="utf-8")) for d in days}
    js = "window.PUZZLES = " + json.dumps(puzzles, ensure_ascii=False) + ";\n"
    (DATA_DIR / "puzzles.js").write_text(js, encoding="utf-8")


def days_between(start: date, end: date):
    if start > end:  # accept the dates in either order
        start, end = end, start
    current = start
    while current <= end:
        yield current.isoformat()
        current += timedelta(days=1)


def missing_days_until_today() -> list:
    """Every day after the newest saved puzzle, up to and including today.

    If nothing is saved yet, this is just today. So after a few days away,
    one run fills in all the days you missed.
    """
    saved = [p.stem for p in DATA_DIR.glob("*.json") if p.stem != "index"] if DATA_DIR.exists() else []
    today = date.today()
    if not saved:
        return [today.isoformat()]
    latest = date.fromisoformat(max(saved))
    if latest >= today:
        return []
    return list(days_between(latest + timedelta(days=1), today))


def needs_update(path: Path) -> bool:
    """A saved file is out of date if it was saved before pictures were added."""
    try:
        return "images" not in json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True


def outdated_days() -> list:
    """Saved days that predate picture support, so they get re-fetched once."""
    if not DATA_DIR.exists():
        return []
    return [p.stem for p in DATA_DIR.glob("*.json") if p.stem != "index" and needs_update(p)]


def main(argv: list) -> int:
    if not argv:
        days = sorted(set(missing_days_until_today()) | set(outdated_days()))
        if not days:
            print("already up to date")
            update_index()
            return 0
    elif len(argv) == 1:
        days = [argv[0]]
    else:
        days = list(days_between(date.fromisoformat(argv[0]), date.fromisoformat(argv[1])))

    fetched = 0
    for day in days:
        path = DATA_DIR / f"{day}.json"
        if path.exists() and not needs_update(path):
            print(f"{day}: already saved, skipping")
            continue
        try:
            raw = fetch_raw(day)
            puzzle = normalize(day, raw)
            attach_images(day, raw, puzzle)
        except Exception as exc:  # keep going through the range even if one day fails
            print(f"{day}: FAILED ({exc})")
            continue
        save(day, puzzle)
        fetched += 1
        note = f" ({len(puzzle['warnings'])} warnings)" if puzzle["warnings"] else ""
        print(f"{day}: saved '{puzzle['title']}' {puzzle['width']}x{puzzle['height']}{note}")
        time.sleep(DELAY_SECONDS)

    update_index()
    print(f"done, {fetched} new puzzle(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
