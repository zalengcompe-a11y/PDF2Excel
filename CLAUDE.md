# PDF2Excel — Project Context for Claude

## สิ่งที่ต้องรู้ก่อนช่วย

- โปรเจคนี้เป็น **cross-platform PDF→Excel converter** รองรับภาษาไทย
- GitHub: https://github.com/zalengcompe-a11y/PDF2Excel (public, MIT)
- Latest release: v2.0.1
- **อย่าแนะนำให้เริ่มใหม่** — architecture ทำงานได้ดีแล้ว ให้ต่อยอดจากของเดิม

## Architecture (6 ไฟล์หลัก)

| ไฟล์ | หน้าที่ |
|---|---|
| `gui.py` | tkinter GUI, threading + queue |
| `pdf2excel.py` | CLI entry point |
| `extractor.py` | PDF extraction (pymupdf default, pdfplumber fallback) |
| `formatter.py` | Excel output (openpyxl) |
| `thai_utils.py` | Thai PUA encoding fix (U+F700–U+F71B → standard Thai) |
| `tests/` | 87 pytest tests, all passing |

## ก่อนแก้โค้ด

```bash
pytest   # ต้องผ่านทั้งหมดก่อน commit
```

## Release workflow

```bash
git tag v1.x.x && git push origin v1.x.x
# GitHub Actions build Win + Mac อัตโนมัติ
```

## Gotchas สำคัญ

- **Build ต้องทำนอก OneDrive** — `C:\Projects\PDF2Excel\` ไม่ใช่ Desktop
- **Thai font:** ใช้ `_thai_font()` ใน gui.py เท่านั้น อย่า hardcode font name
- **File open cross-platform:** ใช้ `sys.platform` check ใน `_open_output()`
- **PyInstaller:** ต้อง `collect_all('openpyxl')` และ `collect_all('et_xmlfile')` ไม่งั้น NoneType error
- **`.sh` files:** ต้องเป็น LF เสมอ (`.gitattributes` จัดการแล้ว)
