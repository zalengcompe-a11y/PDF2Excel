# PDF2Excel — แปลง PDF เป็น Excel

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)

> [🇹🇭 ภาษาไทย](#ภาษาไทย) · [🇬🇧 English](#english)

---

## ภาษาไทย

### เกี่ยวกับโปรแกรม

เครื่องมือแปลงไฟล์ PDF ที่มีตารางข้อมูล (รองรับภาษาไทย) ให้เป็นไฟล์ Excel (.xlsx)  
รองรับ PDF ที่มีข้อความแบบ selectable (ไม่ใช่ PDF ที่ scan มาเป็นรูปภาพ)

### คุณสมบัติหลัก

- ✅ รองรับภาษาไทย — แก้ปัญหา font encoding แบบ Microsoft PUA (Angsana / Cordia / Browallia)
- ✅ กรองลายน้ำออกอัตโนมัติ — ตรวจจับข้อความที่หมุนเอียง (watermark) แล้วตัดออก
- ✅ ชื่อไฟล์ภาษาไทย — เปิดไฟล์ PDF ที่ตั้งชื่อเป็นภาษาไทยได้
- ✅ กำหนดช่วงหน้า — เลือก start page / end page ได้
- ✅ ข้าม header ซ้ำ — ตัด header row ที่ซ้ำกันในแต่ละหน้าออกอัตโนมัติ
- ✅ ใช้งานได้ 2 แบบ — GUI (หน้าต่าง) และ CLI (command line)
- ✅ Excel สวยงาม — header สีน้ำเงิน, alternating rows, freeze pane, auto filter

### วิธีใช้งาน (สำหรับทีม — ไม่ต้องติดตั้ง Python)

1. ดาวน์โหลด `PDF2Excel_vXXXXXXXX.zip` จาก [Releases](../../releases)
2. แตกไฟล์ zip
3. ดับเบิลคลิก **`PDF2Excel.exe`**
4. คลิก **Browse** เลือกไฟล์ PDF
5. ตั้งค่าตามต้องการ แล้วคลิก **Convert to Excel**

### ตัวเลือกใน GUI

| ตัวเลือก | คำอธิบาย |
|---|---|
| Start page | หน้าเริ่มต้น (default: 1) |
| End page | หน้าสุดท้าย (default: หน้าสุดท้ายของไฟล์) |
| Skip rows | ข้ามกี่แถวแรกของผลลัพธ์ |
| Sheet name | ชื่อ worksheet ใน Excel (default: Data) |

### วิธีใช้งานแบบ CLI (สำหรับ Developer)

```bash
# แปลงทั้งไฟล์
python pdf2excel.py input.pdf

# กำหนด output ชื่อเอง
python pdf2excel.py input.pdf output.xlsx

# เลือกช่วงหน้า
python pdf2excel.py input.pdf --start-page 5 --end-page 50

# ข้าม header row แรก
python pdf2excel.py input.pdf --skip-rows 1

# ตั้งชื่อ sheet
python pdf2excel.py input.pdf --sheet "ข้อมูลยอดขาย"

# ดู log ละเอียด
python pdf2excel.py input.pdf --verbose
```

### โครงสร้างโปรเจค

```
PDF2Excel/
├── gui.py              — หน้าต่าง GUI (tkinter)
├── pdf2excel.py        — CLI entry point
├── extractor.py        — engine ดึงข้อมูลจาก PDF (PyMuPDF / pdfplumber)
├── formatter.py        — จัดรูปแบบและบันทึก Excel
├── thai_utils.py       — แก้ไข Thai PUA encoding
├── requirements.txt    — dependencies
├── launch.bat          — รัน GUI (auto-install Python ถ้ายังไม่มี)
├── build.bat           — สร้าง .exe สำหรับแจกทีม
└── PDF2Excel.spec      — PyInstaller config
```

### สำหรับ Developer — ติดตั้งและรันจาก source

```bash
# 1. Clone repo
git clone https://github.com/zalengcompe-a11y/PDF2Excel.git
cd PDF2Excel

# 2. ติดตั้ง dependencies
pip install -r requirements.txt

# 3. รัน GUI
python gui.py

# หรือรัน CLI
python pdf2excel.py input.pdf
```

### สร้าง .exe เพื่อแจกทีม

```bash
# Clone มาไว้นอก OneDrive ก่อน (หลีกเลี่ยง permission error)
cd C:\Projects
git clone https://github.com/zalengcompe-a11y/PDF2Excel.git
cd PDF2Excel

# Build
build.bat
# ได้ไฟล์ PDF2Excel_vYYYYMMDD.zip — นำไปแจกทีมได้เลย
```

### Dependencies

| Package | เวอร์ชัน | หน้าที่ |
|---|---|---|
| pymupdf | ≥ 1.23.0 | อ่าน PDF, รองรับ Thai Unicode |
| pdfplumber | ≥ 0.10.0 | fallback engine สำหรับ PDF ภาษาละติน |
| openpyxl | ≥ 3.1.2 | เขียนไฟล์ Excel |
| tqdm | ≥ 4.65.0 | แสดง progress bar ใน CLI |

---

## English

### About

A robust tool for converting native (text-selectable) PDF files containing tables into formatted Excel (.xlsx) files.  
Designed for Thai-language PDFs but works with any language.

### Features

- ✅ Thai language support — fixes Microsoft PUA font encoding (Angsana / Cordia / Browallia family)
- ✅ Watermark filtering — detects and removes rotated watermark text automatically
- ✅ Thai filenames — opens PDF files with Thai characters in the filename
- ✅ Page range selection — specify start and end pages
- ✅ Duplicate header removal — strips repeated header rows that appear on every page
- ✅ Two modes — GUI (desktop window) and CLI (command line)
- ✅ Formatted Excel output — blue header, alternating rows, freeze pane, auto filter

### Usage (for team members — no Python required)

1. Download `PDF2Excel_vXXXXXXXX.zip` from [Releases](../../releases)
2. Extract the zip file
3. Double-click **`PDF2Excel.exe`**
4. Click **Browse** to select a PDF file
5. Configure options and click **Convert to Excel**

### GUI Options

| Option | Description |
|---|---|
| Start page | First page to extract (default: 1) |
| End page | Last page to extract (default: last page) |
| Skip rows | Drop the first N rows from output |
| Sheet name | Excel worksheet name (default: Data) |

### CLI Usage (for developers)

```bash
# Convert entire file
python pdf2excel.py input.pdf

# Specify output filename
python pdf2excel.py input.pdf output.xlsx

# Extract specific page range
python pdf2excel.py input.pdf --start-page 5 --end-page 50

# Skip the first header row
python pdf2excel.py input.pdf --skip-rows 1

# Custom sheet name
python pdf2excel.py input.pdf --sheet "Sales Data"

# Enable verbose logging
python pdf2excel.py input.pdf --verbose
```

### Project Structure

```
PDF2Excel/
├── gui.py              — tkinter GUI frontend
├── pdf2excel.py        — CLI entry point
├── extractor.py        — PDF extraction engine (PyMuPDF / pdfplumber)
├── formatter.py        — Excel formatting and output
├── thai_utils.py       — Thai PUA encoding fix
├── requirements.txt    — Python dependencies
├── launch.bat          — Run GUI (auto-installs Python if missing)
├── build.bat           — Build standalone .exe for distribution
└── PDF2Excel.spec      — PyInstaller build configuration
```

### Developer Setup

```bash
# 1. Clone the repository
git clone https://github.com/zalengcompe-a11y/PDF2Excel.git
cd PDF2Excel

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run GUI
python gui.py

# Or run CLI
python pdf2excel.py input.pdf
```

### Building the .exe for distribution

```bash
# Clone outside OneDrive to avoid permission errors during build
cd C:\Projects
git clone https://github.com/zalengcompe-a11y/PDF2Excel.git
cd PDF2Excel

# Build
build.bat
# Output: PDF2Excel_vYYYYMMDD.zip — ready to share with the team
```

### Dependencies

| Package | Version | Purpose |
|---|---|---|
| pymupdf | ≥ 1.23.0 | PDF reading with correct Thai Unicode support |
| pdfplumber | ≥ 0.10.0 | Fallback engine for Latin PDFs |
| openpyxl | ≥ 3.1.2 | Excel file writing |
| tqdm | ≥ 4.65.0 | CLI progress bar |

### Requirements

- **Runtime (end users):** None — the distributed `.exe` is fully self-contained
- **Development:** Python 3.10 or later

### License

MIT License — see [LICENSE](LICENSE) for details.

### Known Limitations

- Scanned PDFs (image-only) are not supported — the PDF must contain selectable text
- Very large PDFs (500+ pages) may take several minutes to process
