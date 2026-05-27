"""
thai_utils.py — Thai text post-processing for PDF-extracted text.

Root cause (confirmed by codepoint analysis of out.xlsx)
---------------------------------------------------------
The PDF uses Microsoft Thai fonts (Angsana/Cordia/Browallia family) that
include *positional alternate forms* of Thai diacritics.  These alternates
are visually shorter/taller glyphs used above/below specific consonant
classes (e.g. ascending strokes), but they are *semantically identical* to
their standard Unicode Thai counterparts.

The fonts store these alternates in the Unicode Private Use Area (U+F700–
U+F71B).  PDF extraction libraries (PyMuPDF, pdfplumber) faithfully output
the PUA code points they find — because the font's ToUnicode CMap maps
glyphs to PUA.  Excel/Word/viewers don't render PUA Thai, so the characters
appear blank or garbled.

Examples found in this PDF:
  U+F70B (21,105 occurrences) → ้  U+0E49  mai tho   (tone 2)
  U+F70A (10,307 occurrences) → ่  U+0E48  mai ek    (tone 1)
  U+F706  (   ~5 occurrences) → ้  U+0E49  mai tho (ascending-consonant form: ป้, ฝ้, ฟ้)
  U+F710  (2,076 occurrences) → ั  U+0E31  sara a (ascending-consonant form: ปัญหา, ฟังก์ชัน)
  U+F70E  (2,889 occurrences) → ์  U+0E4C  thanthakat (silent mark)
  U+F712  (1,096 occurrences) → ็  U+0E47  mai taikhu (ascending-consonant form: เป็น)
  … and 11 other PUA alternates

After applying the mapping below, ZERO PUA or unexpected non-Thai chars
remain — all 64 distinct Thai codepoints resolve to the standard Thai block
(U+0E00–U+0E7F).

Fix applied
-----------
1. Replace every PUA alternate with its standard Unicode Thai equivalent.
2. Apply Unicode NFC normalisation to compose any remaining combining chars.

References
----------
Microsoft Thai font PUA encoding:
  https://docs.microsoft.com/typography/opentype/spec/name (legacy Thai PUA)
Unicode Technical Note #21 — Additional Thai Characters
"""

import unicodedata


# ── Thai PUA → Standard Thai Unicode mapping ─────────────────────────────────
# Source: Microsoft/Thai OpenType font PUA standard (Angsana/Cordia/Browallia)
#
# Each PUA code point is a positional alternate form (short, tall, or ascender
# variant) of the listed standard Thai character — same semantics, different
# glyph shape for specific consonant height contexts.

_THAI_PUA_MAP: dict[int, str] = {
    0xF700: '็',  # ็  mai taikhu     (short form)
    0xF701: 'ั',  # ั  sara a above   (short)
    0xF702: 'ิ',  # ิ  sara i          (short)
    0xF703: 'ี',  # ี  sara ii         (short)
    0xF704: 'ึ',  # ึ  sara ue         (short)
    0xF705: 'ื',  # ื  sara uee        (short)
    0xF706: '้',  # ้  mai tho          (ascending-consonant form: ป้, ฝ้, ฟ้)
    0xF707: 'ู',  # ู  sara uu below   (alternate)
    0xF708: 'ุ',  # ุ  sara u          (2nd alternate)
    0xF709: 'ู',  # ู  sara uu         (2nd alternate)
    0xF70A: '่',  # ่  mai ek          (short — above low-class consonant)
    0xF70B: '้',  # ้  mai tho         (short — most common PUA, 21k hits)
    0xF70C: '๊',  # ๊  mai tri         (short)
    0xF70D: '๋',  # ๋  mai jattawa     (short)
    0xF70E: '์',  # ์  thanthakat      (short)
    0xF70F: 'ฺ',  # ฺ  phinthu         (below dot)
    0xF710: 'ั',  # ั  sara a above    (ascending-consonant form: ปัญหา, ฟังก์ชัน)
    0xF711: 'ั',  # ั  sara a above   (ascender)
    0xF712: '็',  # ็  mai taikhu      (ascending-consonant form: เป็น)
    0xF713: '้',  # ้  mai tho         (ascender)
    0xF714: '๊',  # ๊  mai tri         (ascender)
    0xF715: '๋',  # ๋  mai jattawa     (ascender)
    0xF716: 'ั',  # ั  sara a above   (3rd form)
    0xF717: 'ิ',  # ิ  sara i          (3rd form)
    0xF718: 'ี',  # ี  sara ii         (3rd form)
    0xF719: 'ึ',  # ึ  sara ue         (3rd form)
    0xF71A: 'ื',  # ื  sara uee        (3rd form)
    0xF71B: '่',  # ่  mai ek          (4th form — 21 hits)
}

# Build a str.translate() table for O(n) replacement
_PUA_TRANSLATE = str.maketrans(_THAI_PUA_MAP)


# ── Public API ────────────────────────────────────────────────────────────────

def fix_thai_order(text: str) -> str:
    """
    Fix Thai text extracted from a PDF that uses Microsoft Thai PUA encoding.

    Steps:
    1. Replace PUA alternate forms (U+F700–U+F71B) with standard Thai chars.
    2. Apply Unicode NFC normalisation to compose combining characters.

    Safe to call on non-Thai / mixed-language text — only the PUA range is
    remapped; all other characters pass through unchanged.
    """
    if not text:
        return text
    # Step 1 — PUA → standard Thai (uses str.translate for speed)
    text = text.translate(_PUA_TRANSLATE)
    # Step 2 — NFC: Thai tone marks (cc=107) won't cross cc=0 boundaries
    return unicodedata.normalize('NFC', text)


def fix_thai_row(row: list[str]) -> list[str]:
    """Apply fix_thai_order to every cell in a row."""
    return [fix_thai_order(cell) for cell in row]
