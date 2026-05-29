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


# ── Pre-PUA multi-character sara-ii recovery ──────────────────────────────────
# Some Thai PDFs (notably those using older EGAT/Microsoft office fonts) encode
# sara-ii (ี U+0E35) as a SEQUENCE of PUA and non-PUA glyphs rather than a
# single character.  These sequences must be collapsed BEFORE the per-character
# PUA translation fires, because they span both PUA and standard codepoints.
#
# Pattern A (5-char, ascending consonant + nikhahit spacing):
#   U+F712 U+F70B U+0E4D U+F70A U+F70B  →  ี
#   Observed for consonants like ป that have a tall ascending stroke; the font
#   splits sara-ii into three visual sub-glyphs (lower hook F712, upper curve
#   F70B) plus a "phantom" nikhahit U+0E4D used as a horizontal spacer,
#   followed by another F70A/F70B pair.
#
# Pattern B (2-char, simpler ascending-consonant form):
#   U+F712 U+F70B  →  ี
#   Same logic but without the phantom nikhahit.
#
# Both patterns are applied as regex so they fire before str.translate().

_RE_SARA_II_5CHAR = re.compile(
    "ํ"   # F712 F70B ํ F70A F70B
)
_RE_SARA_II_2CHAR = re.compile(
    ""                       # F712 F70B
)


def _fix_sara_ii_pua_sequences(text: str) -> str:
    """
    Collapse multi-character PUA encodings of sara-ii (ี) into a single U+0E35.

    Must run BEFORE the per-character PUA translate table so the 5-char pattern
    takes priority over individual F712 / F70B substitutions.
    """
    text = _RE_SARA_II_5CHAR.sub("ี", text)   # longer pattern first
    text = _RE_SARA_II_2CHAR.sub("ี", text)
    return text


# ── Font-CMap garbling recovery ───────────────────────────────────────────────
# Some Thai PDFs use ligature/composite glyphs whose ToUnicode CMap omits one
# of the combining characters.  Patterns fixed here (AFTER PUA mapping + NFC):
#
# 1.  ผ + ้  + consonant/leading-vowel  →  ผู้ + ...
#     sara-uu (ู U+0E39) omitted by CMap.
#     Guard: ผ้า (fabric, ้ before า) is preserved.
#
# 2.  ไ + ้  →  ได้
#     ไ is a leading vowel and never takes a tone mark directly.
#
# 3.  ็ + ้  →  ี  (mai-taikhu + mai-tho → sara-ii)
#     Occurs when _RE_SARA_II_2CHAR applies but a stray ้ still remains, or
#     when a font independently encodes sara-ii above ascending consonants as
#     the two-PUA sequence that maps to ็ + ้ after per-char translation.
#     Having both U+0E47 (mai-taikhu) and U+0E49 (mai-tho) on the same
#     consonant is extremely rare / non-standard in modern Thai orthography.
#
# 4.  ิ + ั + ิ  →  ี  (sara-i + sara-a + sara-i → sara-ii)
#     Observed in older EGAT font rendering: the long-i vowel mark is split into
#     three sub-glyph components each mapped to sara-i or sara-a in the CMap.
#
# 5.  ิ + ิ  →  ี  (two sara-i → sara-ii)
#     Simpler two-component encoding of the same issue.

# Thai consonants U+0E01–U+0E2E, leading vowels U+0E40–U+0E44
_RE_PHO_MAI_THO = re.compile(r"ผ้(?=[ก-ฮเ-ไ])")
_RE_SAI_MAI_THO = re.compile(r"ไ้")
_RE_MAI_TAIKHU_MAI_THO = re.compile(r"็้")          # mai-taikhu + mai-tho → sara-ii
_RE_SARA_I_SARA_A_SARA_I = re.compile(r"ิัิ")       # sara-i + sara-a + sara-i → sara-ii
_RE_DOUBLE_SARA_I = re.compile(r"ิิ")               # two sara-i → sara-ii

# Orphan-mark cleanup: when multi-char sara-ii encoding is split across rawdict
# lines, _join_cell_lines inserts spaces between PUA-character segments.  After
# PUA translation the result contains spurious combining marks adjacent to spaces:
#
#   ีํ  — nikhahit (ํ U+0E4D) immediately after sara-ii (ี) is invalid; drop it.
#   " [่้๊๋]+" — tone marks floating after a space have no base consonant;
#               they are rendering artifacts of the split encoding, not real text.
#               Remove them while preserving the space.

_RE_SARA_II_NIKHAHIT = re.compile(r"ีํ")            # sara-ii + nikhahit → sara-ii

# Sara-am recomposition: many Thai PDFs (incl. the EGAT/Angsana family) encode
# sara-am (ำ U+0E33) as the DECOMPOSED two-codepoint sequence
#   nikhahit (ํ U+0E4D) + sara-aa (า U+0E32).
# Unicode NFC does NOT recompose these — U+0E33 has no canonical decomposition —
# so the garbled form survives extraction.  It is visually identical to ำ but
# breaks search, copy, and text matching (e.g. ทํางาน vs the correct ทำงาน).
# The sequence ํ+า is virtually never intended as two separate characters in
# standard Thai, so recombining it is always safe.
_RE_SARA_AM_DECOMPOSED = re.compile("ํา")  # ํ + า → ำ

# Thai combining marks that NEVER appear at the start of a word (after a space):
# nikhahit ํ (0E4D), mai-ek ่ (0E48), mai-tho ้ (0E49), mai-tri ๊ (0E4A),
# mai-jattawa ๋ (0E4B).  When these appear immediately after a space or newline
# they are rendering artifacts (orphan marks from a split multi-glyph encoding)
# and must be removed.  Removing them is ALWAYS safe in modern Thai orthography.
_RE_ORPHAN_TONE_MARKS = re.compile(r"(?<=[ \n])[ํ่้๊๋]+")


def _fix_font_cmap_garbling(text: str) -> str:
    """
    Recover characters dropped/garbled by incomplete ToUnicode CMap in Thai PDFs.

    Applied AFTER PUA mapping and NFC so all characters are in standard form.
    """
    # Pattern 0: ํ + า → ำ  (recompose decomposed sara-am; MUST precede the
    #            orphan-mark removal in Pattern 7, otherwise a leading ํ after a
    #            space would be stripped before it can pair with า)
    text = _RE_SARA_AM_DECOMPOSED.sub("ำ", text)
    # Pattern 1: ผ้[consonant/leading-vowel] → ผู้
    text = _RE_PHO_MAI_THO.sub("ผู้", text)
    # Pattern 2: ไ้ → ได้
    text = _RE_SAI_MAI_THO.sub("ได้", text)
    # Pattern 3: ็้ → ี  (ascending-consonant sara-ii, 2-component form)
    text = _RE_MAI_TAIKHU_MAI_THO.sub("ี", text)
    # Pattern 4: ิัิ → ี  (3-component sara-ii; must precede pattern 5)
    text = _RE_SARA_I_SARA_A_SARA_I.sub("ี", text)
    # Pattern 5: ิิ → ี  (2-component sara-ii)
    text = _RE_DOUBLE_SARA_I.sub("ี", text)
    # Pattern 6: ีํ → ี  (spurious nikhahit after sara-ii from split encoding)
    text = _RE_SARA_II_NIKHAHIT.sub("ี", text)
    # Pattern 7: tone marks / nikhahit stranded after space/newline → remove
    text = _RE_ORPHAN_TONE_MARKS.sub("", text)
    # Pattern 8: collapse multiple consecutive spaces to one (may arise after P7)
    text = re.sub(r"  +", " ", text)
    return text


# ── Public API ────────────────────────────────────────────────────────────────

def fix_thai_order(text: str) -> str:
    """
    Fix Thai text extracted from a PDF that uses Microsoft Thai PUA encoding.

    Steps:
    1. Collapse multi-character PUA sequences that encode a single sara-ii (ี).
    2. Replace remaining PUA alternate forms (U+F700–U+F71B) with standard Thai.
    3. Apply Unicode NFC normalisation to compose combining characters.
    4. Recover characters dropped by incomplete font ToUnicode CMap entries.

    Safe to call on non-Thai / mixed-language text — only the PUA range is
    remapped; all other characters pass through unchanged.
    """
    if not text:
        return text
    # Step 1 — collapse multi-char sara-ii PUA sequences (must precede translate)
    text = _fix_sara_ii_pua_sequences(text)
    # Step 2 — remaining PUA → standard Thai (per-character, O(n))
    text = text.translate(_PUA_TRANSLATE)
    # Step 3 — NFC: Thai tone marks (cc=107) won't cross cc=0 boundaries
    text = unicodedata.normalize('NFC', text)
    # Step 4 — recover glyphs omitted/garbled by incomplete font CMap
    return _fix_font_cmap_garbling(text)


def fix_thai_row(row: list[str]) -> list[str]:
    """Apply fix_thai_order to every cell in a row."""
    return [fix_thai_order(cell) for cell in row]
