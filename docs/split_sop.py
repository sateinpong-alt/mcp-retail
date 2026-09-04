import re, json, pathlib

src = pathlib.Path("/home/claude/sop_source.md").read_text(encoding="utf-8")
root = pathlib.Path("/home/claude/retail-sop-toolkit")
sopdir = root / "mcp" / "data" / "sops"

# แยกบล็อกที่ขึ้นต้นด้วย "## PU-xx ..." หรือ "## FS-xx ..."
pattern = re.compile(r"^## ((?:PU|FS)-\d{2}) (.+?)$", re.M)
matches = list(pattern.finditer(src))

index = []
for i, m in enumerate(matches):
    sop_id, title = m.group(1), m.group(2).strip()
    start = m.start()
    end = matches[i + 1].start() if i + 1 < len(matches) else src.index("# ส่วนที่ 4")
    body = src[start:end].strip()
    body = re.sub(r"\n---\s*$", "", body).strip()
    dept = "purchasing" if sop_id.startswith("PU") else "storefront"
    fname = f"{sop_id}.md"
    (sopdir / fname).write_text(body + "\n", encoding="utf-8")
    index.append({
        "id": sop_id,
        "title": title,
        "department": dept,
        "file": f"sops/{fname}",
        "keywords": [],
    })

(root / "mcp" / "data" / "sop_index.json").write_text(
    json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

# REFERENCE.md ของแต่ละ skill = หัวข้อของฝั่งนั้นต่อกัน + ภาคผนวก
head = src[: src.index("# ส่วนที่ 2")].strip()
tail = src[src.index("# ส่วนที่ 4") :].strip()

for dept, prefix, name in [("purchasing", "PU", "retail-purchasing"),
                           ("storefront", "FS", "retail-storefront")]:
    parts = [b for b in index if b["department"] == dept]
    body = "\n\n---\n\n".join(
        (sopdir / f'{p["id"]}.md').read_text(encoding="utf-8").strip() for p in parts)
    out = f"{head}\n\n---\n\n{body}\n\n---\n\n{tail}\n"
    (root / "skills" / name / "REFERENCE.md").write_text(out, encoding="utf-8")

print(json.dumps(index, ensure_ascii=False, indent=1))
