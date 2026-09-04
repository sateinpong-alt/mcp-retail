"""
Retail SOP MCP Server
เสิร์ฟ SOP ฝ่ายจัดซื้อและหน้าร้านของร้านค้าปลีก ให้ Claude เรียกใช้เป็น tool

รันในเครื่อง:      python server.py
รันบน Railway:     ตั้ง start command เป็น `python server.py` (อ่าน PORT จาก env)
Transport:         streamable-http  ->  https://<domain>/mcp
"""

import json
import os
import pathlib
from datetime import datetime, timezone
from typing import Optional

# mcp SDK 2.x: FastMCP ถูกเปลี่ยนชื่อเป็น MCPServer
# ถ้าใช้ SDK รุ่น 1.x ให้เปลี่ยนสองบรรทัดล่างเป็น
#   from mcp.server.fastmcp import FastMCP as MCPServer
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

DATA = pathlib.Path(__file__).parent / "data"
LOG_PATH = pathlib.Path(os.environ.get("LOG_PATH", "/tmp/retail_sop_log.jsonl"))

mcp = MCPServer(
    "retail-sop",
    instructions=(
        "SOP ร้านค้าปลีก ฝั่งจัดซื้อ (PU-01..PU-07) และหน้าร้าน (FS-01..FS-08) "
        "ให้เรียก get_sop อ่านเนื้อหาจริงก่อนตอบทุกครั้ง และเรียก get_approval_authority "
        "ก่อนบอกใครว่าอนุมัติอะไรได้ ห้ามตอบวงเงินหรือเกณฑ์จากความจำ"
    ),
)


# ---------- helpers ----------

def _index() -> list[dict]:
    return json.loads((DATA / "sop_index.json").read_text(encoding="utf-8"))


def _matrix() -> dict:
    return json.loads((DATA / "approval_matrix.json").read_text(encoding="utf-8"))


def _body(entry: dict) -> str:
    return (DATA / entry["file"]).read_text(encoding="utf-8")


def _fmt_amount(v: Optional[float]) -> str:
    return "ไม่จำกัด" if v is None else f"{v:,.0f} บาท"


# ---------- read tools ----------

@mcp.tool()
def list_sops(department: Optional[str] = None) -> str:
    """รายชื่อ SOP ทั้งหมดพร้อมรหัส ใช้เมื่อต้องการรู้ว่ามีมาตรฐานเรื่องอะไรบ้าง
    department: purchasing (จัดซื้อ) หรือ storefront (หน้าร้าน) เว้นว่าง = ทั้งหมด
    """
    rows = _index()
    if department:
        dept = department.strip().lower()
        rows = [r for r in rows if r["department"] == dept]
        if not rows:
            return "ไม่พบแผนกนี้ ใช้ได้เฉพาะ purchasing หรือ storefront"
    out = ["| รหัส | เรื่อง | แผนก |", "|---|---|---|"]
    out += [f'| {r["id"]} | {r["title"]} | {r["department"]} |' for r in rows]
    return "\n".join(out)


@mcp.tool()
def get_sop(sop_id: str) -> str:
    """ดึงเนื้อหา SOP ฉบับเต็มตามรหัส เช่น PU-04 หรือ FS-03
    เรียกก่อนตอบทุกครั้งที่ต้องอ้างมาตรฐานของร้าน อย่าตอบจากความจำ
    """
    key = sop_id.strip().upper().replace(" ", "")
    for r in _index():
        if r["id"] == key:
            return _body(r)
    ids = ", ".join(r["id"] for r in _index())
    return f"ไม่พบ SOP รหัส {sop_id}\nรหัสที่มี: {ids}"


@mcp.tool()
def search_sop(query: str) -> str:
    """ค้นหา SOP จากคำค้น เช่น ตรวจรับ ส่งกะ ของหาย วางบิล ตั้งราคา
    คืนค่าเรียงตามความเกี่ยวข้อง ใช้เมื่อไม่รู้ว่าเรื่องนี้อยู่ SOP ข้อไหน
    """
    q = query.strip().lower()
    if not q:
        return "ระบุคำค้นด้วย"
    scored = []
    for r in _index():
        score = 0
        if q in r["title"].lower():
            score += 5
        for k in r["keywords"]:
            if q in k.lower() or k.lower() in q:
                score += 3
        body = _body(r).lower()
        score += body.count(q)
        if score:
            scored.append((score, r))
    if not scored:
        return f"ไม่พบ SOP ที่ตรงกับ '{query}' ลองใช้ list_sops ดูรายการทั้งหมด"
    scored.sort(key=lambda x: -x[0])
    lines = [f"ผลค้นหา '{query}':"]
    for score, r in scored[:5]:
        lines.append(f'- {r["id"]} {r["title"]} ({r["department"]}, คะแนน {score})')
    lines.append("\nเรียก get_sop ด้วยรหัสที่ตรงที่สุดเพื่ออ่านเนื้อหาเต็ม")
    return "\n".join(lines)


@mcp.tool()
def get_approval_authority(topic: str, amount: Optional[float] = None) -> str:
    """ตรวจว่าเรื่องนี้ใครมีอำนาจอนุมัติ และเกินอำนาจพนักงานหน้าร้านหรือไม่
    topic: purchase_order | customer_recovery | stock_adjustment | price_change | cash_variance
    amount: มูลค่าเป็นบาท (ถ้ามี)
    ต้องเรียกทุกครั้งก่อนบอกลูกค้าหรือพนักงานว่าทำอะไรได้ ห้ามเดาวงเงินเอง
    """
    m = _matrix()
    key = topic.strip().lower()
    if key not in m or key.startswith("_"):
        valid = ", ".join(k for k in m if not k.startswith("_") and k != "escalate_always")
        return f"topic ไม่ถูกต้อง ใช้ได้: {valid}"

    block = m[key]
    lines = [f'เรื่อง: {key} (อ้างอิง {block["sop"]})']
    for t in block["tiers"]:
        scope = f' — {t["scope"]}' if t.get("scope") else ""
        limit = "เกินกว่านั้น" if t["max_amount"] is None else f'ไม่เกิน {_fmt_amount(t["max_amount"])}'
        lines.append(f'- {limit}: {t["approver"]}{scope}')

    if amount is not None:
        chosen = next(
            (t for t in block["tiers"] if t["max_amount"] is None or amount <= t["max_amount"]),
            block["tiers"][-1],
        )
        lines.append(f'\n>> มูลค่า {amount:,.0f} บาท ต้องอนุมัติโดย: {chosen["approver"]}')

    lines.append("\nเคสที่ต้องส่งต่อเสมอ ไม่ว่ามูลค่าเท่าไร:")
    lines += [f'- {c["case"]} -> {c["route"]}' for c in m["escalate_always"]]
    return "\n".join(lines)


@mcp.tool()
def get_checklist(name: str) -> str:
    """ดึงเช็กลิสต์ปฏิบัติงานประจำวัน
    name: opening (เปิดร้าน) | closing (ปิดร้าน) | receiving (ตรวจรับของ) | handover (ส่งกะ)
    """
    mapping = {
        "opening": "FS-01",
        "closing": "FS-06",
        "receiving": "PU-04",
        "handover": "FS-03",
    }
    key = name.strip().lower()
    if key not in mapping:
        return "name ใช้ได้เฉพาะ: opening, closing, receiving, handover"
    return get_sop(mapping[key])


# ---------- write tool ----------

@mcp.tool()
def log_exception(
    sop_id: str,
    summary: str,
    action_taken: str,
    approved_by: str,
    amount: Optional[float] = None,
) -> str:
    """บันทึกเคสที่ทำนอกเหนือ SOP หรือเคสที่ต้องมีผู้อนุมัติ เช่น เงินขาด ปรับยอดสต็อก
    ชดเชยลูกค้า รับของทั้งที่มีปัญหา

    เป็นการเขียนข้อมูล ให้ยืนยันกับผู้ใช้ก่อนเรียกทุกครั้ง และห้ามกรอกชื่อผู้อนุมัติเอง
    ถ้าผู้ใช้ยังไม่ได้ระบุว่าใครอนุมัติ ให้ถามก่อน
    """
    if not approved_by.strip():
        return "ต้องระบุชื่อผู้อนุมัติก่อนบันทึก"
    record = {
        "logged_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sop_id": sop_id.strip().upper(),
        "summary": summary.strip(),
        "action_taken": action_taken.strip(),
        "approved_by": approved_by.strip(),
        "amount": amount,
    }
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return "บันทึกแล้ว:\n" + json.dumps(record, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # ตั้ง ALLOWED_HOSTS เป็นโดเมนจริงเมื่อ deploy เช่น myshop-sop.up.railway.app
    # ถ้าเว้นว่าง จะปิด DNS rebinding protection (ใช้ตอนทดสอบในเครื่องเท่านั้น)
    allowed = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h.strip()]
    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=bool(allowed),
        allowed_hosts=allowed,
        allowed_origins=[f"https://{h}" for h in allowed],
    )
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        stateless_http=True,
        transport_security=security,
    )
