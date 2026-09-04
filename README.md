# retail-sop-toolkit

SOP ร้านค้าปลีก ฝั่งจัดซื้อและหน้าร้าน แปลงเป็น 2 skill + MCP server ที่เสิร์ฟตัว SOP เป็น tool
โครงเดียวกับ plugin ที่ใช้กับ Andaman อยู่แล้ว

## โครงสร้างไฟล์

```
retail-sop-toolkit/
├── README.md
├── .claude-plugin/
│   └── plugin.json              # นิยาม plugin: ชี้ไป skill 2 ตัว + URL ของ MCP
├── docs/
│   └── SOP-ฉบับเต็ม.md           # ต้นฉบับที่ใช้แตกเป็นไฟล์ย่อย เก็บไว้อ้างอิง/พิมพ์แจก
├── skills/
│   ├── retail-purchasing/
│   │   ├── SKILL.md             # เมื่อไรให้ทำงาน + กฎที่ห้ามยืดหยุ่น + วิธีตอบ
│   │   └── REFERENCE.md         # SOP ฝั่งจัดซื้อฉบับเต็ม (ใช้ตอนไม่ได้ต่อ MCP)
│   └── retail-storefront/
│       ├── SKILL.md
│       └── REFERENCE.md         # SOP ฝั่งหน้าร้านฉบับเต็ม
└── mcp/
    ├── server.py                # MCP server (streamable HTTP)
    ├── requirements.txt
    ├── Procfile
    ├── railway.json
    ├── .env.example
    └── data/
        ├── sop_index.json       # ทะเบียน SOP + keyword สำหรับค้นหา
        ├── approval_matrix.json # ตารางอำนาจอนุมัติ + เคสที่ต้องส่งต่อเสมอ
        └── sops/
            ├── PU-01.md … PU-07.md
            └── FS-01.md … FS-08.md
```

**หลักที่วางไว้:** เนื้อ SOP อยู่ที่เดียวคือ `mcp/data/sops/` แก้ที่นั่นแล้ว deploy ใหม่
ทุกคนได้ฉบับใหม่พร้อมกัน ส่วน `REFERENCE.md` ใน skill เป็นสำเนาสำรองไว้ใช้ตอนไม่ได้ต่อ MCP
ถ้าแก้ SOP แล้วต้อง sync สำเนานี้ด้วย (สคริปต์แยกไฟล์อยู่ในไฟล์ที่ผมส่งให้แยกต่างหาก)

## Tool ที่ MCP เปิดให้

| Tool | ใช้ทำอะไร |
|---|---|
| `list_sops(department?)` | รายชื่อ SOP ทั้งหมด กรองด้วย `purchasing` / `storefront` |
| `get_sop(sop_id)` | เนื้อหาเต็มตามรหัส เช่น `PU-04`, `FS-03` |
| `search_sop(query)` | ค้นจากคำค้นไทย เช่น "ตรวจรับ" "เงินขาด" "ของหมดอายุ" |
| `get_approval_authority(topic, amount?)` | ใครอนุมัติได้ + เคสที่ต้องส่งต่อเสมอ |
| `get_checklist(name)` | `opening` / `closing` / `receiving` / `handover` |
| `log_exception(...)` | **เขียนข้อมูล** บันทึกเคสนอก SOP ต้องยืนยันก่อนเรียกทุกครั้ง |

## Deploy บน Railway

1. push โฟลเดอร์ `mcp/` ขึ้น GitHub (หรือทั้ง repo แล้วตั้ง root directory เป็น `mcp`)
2. Railway → New Project → Deploy from GitHub repo
3. Variables ที่ต้องตั้ง:
   - `ALLOWED_HOSTS` = โดเมนที่ Railway ให้มา เช่น `myshop-sop.up.railway.app`
     (ถ้าเว้นว่างจะปิด DNS rebinding protection — ใช้ได้แค่ตอนทดสอบในเครื่อง)
   - `LOG_PATH` = ชี้ไป volume ถ้าอยากให้ log ของ `log_exception` อยู่ถาวร
     ค่า default `/tmp/...` จะหายทุกครั้งที่ deploy ใหม่
   - `PORT` Railway ใส่ให้เอง ไม่ต้องตั้ง
4. Settings → Networking → Generate Domain
5. endpoint ที่ได้คือ `https://<domain>/mcp` เอาไปใส่ใน `.claude-plugin/plugin.json`
   แทนที่ `REPLACE-ME` และใส่ใน Claude → Settings → Connectors → Add custom connector

ทดสอบก่อน deploy:
```bash
cd mcp
pip install -r requirements.txt
python server.py          # ขึ้นที่ http://127.0.0.1:8000/mcp
```

## ปรับให้ตรงกับร้านจริงก่อนใช้

ตัวเลขในวงเล็บเหลี่ยม `[...]` ทั้งหมดเป็นค่าตั้งต้น ต้องแทนด้วยของจริง อย่างน้อย 5 จุดนี้
เพราะ skill ถูกสั่งห้ามเดาตัวเลขเอง:

| ไฟล์ | สิ่งที่ต้องแก้ |
|---|---|
| `mcp/data/approval_matrix.json` | วงเงินอนุมัติ PO / ชดเชยลูกค้า / เกณฑ์เงินขาด |
| `mcp/data/sops/PU-01.md` | จำนวนวัน safety stock, รอบสั่งของ |
| `mcp/data/sops/PU-04.md` | เกณฑ์อายุสินค้าคงเหลือตอนรับ, ช่วงเวลารับของ |
| `mcp/data/sops/PU-06.md` | GP% เป้าหมายรายกลุ่มสินค้า |
| `mcp/data/sops/FS-05.md` | เงื่อนไขและจำนวนวันรับคืน/เปลี่ยน |

## หมายเหตุด้านเทคนิค

- เขียนด้วย MCP Python SDK **2.x** ซึ่ง `FastMCP` เปลี่ยนชื่อเป็น `MCPServer` แล้ว
  ถ้า pin เป็น 1.x ให้สลับ import ตามคอมเมนต์บรรทัดบนของ `server.py`
- server รันแบบ `stateless_http=True` เพื่อให้ scale/restart บน Railway ได้โดยไม่ค้าง session
- `log_exception` เขียนลงไฟล์ jsonl ธรรมดา ถ้าจะใช้จริงจังควรต่อ Google Sheet หรือ DB แทน
