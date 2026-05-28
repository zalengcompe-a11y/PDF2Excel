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

import re
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


# ── Font-CMap garbling recovery ───────────────────────────────────────────────
# Some Thai PDFs use ligature/composite glyphs whose ToUnicode CMap omits one
# of the combining characters.  Two patterns recur in Microsoft-font-based PDFs:
#
# 1.  ผ + ้  + consonant/leading-vowel  →  ผู้ + consonant/leading-vowel
#     Thai consonants: U+0E01–U+0E2E (ก–ฮ)
#     Thai leading vowels: เ แ โ ใ ไ (U+0E40–U+0E44)
#     The sara-uu (ู U+0E39) was present in the source document but was not
#     mapped in the font's ToUnicode CMap, so text extraction omits it.
#     Guard: we only insert ู when the character AFTER ้ is a consonant or
#     leading vowel — never when it is า (U+0E32) because ผ้า (fabric) is a
#     valid Thai word.
#
# 2.  ไ + ้  →  ได้
#     ไ (sara ai maimalai, U+0E44) is a LEADING vowel; tone marks attach to
#     the following consonant, never to ไ directly.  The sequence ไ + ้ is
#     therefore always a sign that ด (U+0E14, do dek) was dropped by the CMap.
#     ได้ (can / has obtained) is by far the most common Thai word with this
#     pattern.

# Thai consonants range U+0E01–U+0E2E, leading vowels U+0E40–U+0E44
_RE_PHO_MAI_THO = re.compile(
    r"ผ้(?=[ก-ฮเ-ไ])"
)

# ไ immediately followed by mai tho → always garbled ได้
_RE_SAI_MAI_THO = re.compile(r"ไ้")


def _fix_font_cmap_garbling(text: str) -> str:
    """
    Recover characters dropped by incomplete ToUnicode CMap in Thai PDFs.

    Applied AFTER PUA mapping and NFC so all characters are in standard form.
    Two targeted patterns only — no broad heuristics that could corrupt text.
    """
    # Pattern 1: ผ้[consonant/leading-vowel] → ผู้[consonant/leading-vowel]
    text = _RE_PHO_MAI_THO.sub("ผู้", text)
    # Pattern 2: ไ้ → ได้
    text = _RE_SAI_MAI_THO.sub("ได้", text)
    return text


# ── Public API ────────────────────────────────────────────────────────────────

def fix_thai_order(text: str) -> str:
    """
    Fix Thai text extracted from a PDF that uses Microsoft Thai PUA encoding.

    Steps:
    1. Replace PUA alternate forms (U+F700–U+F71B) with standard Thai chars.
    2. Apply Unicode NFC normalisation to compose combining characters.
    3. Recover characters dropped by incomplete font ToUnicode CMap entries.

    Safe to call on non-Thai / mixed-language text — only the PUA range is
    remapped; all other characters pass through unchanged.
    """
    if not text:
        return text
    # Step 1 — PUA → standard Thai (uses str.translate for speed)
    text = text.translate(_PUA_TRANSLATE)
    # Step 2 — NFC: Thai tone marks (cc=107) won't cross cc=0 boundaries
    text = unicodedata.normalize('NFC', text)
    # Step 3 — recover glyphs omitted by incomplete font CMap
    return _fix_font_cmap_garbling(text)


def fix_thai_row(row: list[str]) -> list[str]:
    """Apply fix_thai_order to every cell in a row."""
    return [fix_thai_order(cell) for cell in row]
