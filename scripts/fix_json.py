"""Fix Chinese quotation marks in JSON data files"""
import json, os

base = os.path.join(os.path.dirname(__file__), "..", "data")
for fname in ["attractions.json", "hotels.json", "foods.json"]:
    fpath = os.path.join(base, fname)
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    # Replace Chinese smart quotes with corner brackets to avoid JSON conflicts
    content = content.replace("“", "「")  # left double quote -> 「
    content = content.replace("”", "」")  # right double quote -> 」
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(content)
    # Verify
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            json.load(f)
        print(f"OK {fname}")
    except json.JSONDecodeError as e:
        print(f"FAIL {fname}: {e}")
