"""
tests/test_thai_utils.py
Unit tests for thai_utils.fix_thai_order()

Run:  pytest tests/test_thai_utils.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from thai_utils import fix_thai_order, fix_thai_row


class TestFixThaiOrder:
    """Tests for PUA → standard Thai mapping."""

    # ── PUA character mapping ──────────────────────────────────────────────

    def test_pua_f70b_mai_tho(self):
        """U+F70B (most common, 21k hits) → ้ U+0E49 mai tho"""
        assert fix_thai_order("") == "้"

    def test_pua_f70a_mai_ek(self):
        """U+F70A → ่ U+0E48 mai ek"""
        assert fix_thai_order("") == "่"

    def test_pua_f710_sara_a_ascending(self):
        """U+F710 → ั U+0E31 sara a (ascending-consonant form: ปัญหา, ฟังก์ชัน)"""
        assert fix_thai_order("") == "ั"

    def test_pua_f70e_thanthakat(self):
        """U+F70E → ์ U+0E4C thanthakat"""
        assert fix_thai_order("") == "์"

    def test_pua_f712_mai_taikhu_ascending(self):
        """U+F712 → ็ U+0E47 mai taikhu (ascending-consonant form: เป็น)"""
        assert fix_thai_order("") == "็"

    def test_pua_f706_mai_tho_ascending(self):
        """U+F706 → ้ U+0E49 mai tho (ascending-consonant form: เป้าหมาย, แฟ้ม)"""
        assert fix_thai_order("") == "้"

    def test_word_pen_ascending(self):
        """เป็น with PUA F712 (ascending maitaikhu above ป) is corrected."""
        assert fix_thai_order("เปน") == "เป็น"

    def test_word_panya_ascending(self):
        """ปัญหา with PUA F710 (ascending sara a above ป) is corrected."""
        assert fix_thai_order("ปญหา") == "ปัญหา"

    def test_word_goal_ascending(self):
        """เป้าหมาย with PUA F706 (ascending mai tho above ป) is corrected."""
        assert fix_thai_order("เปาหมาย") == "เป้าหมาย"

    def test_all_pua_keys_map_to_thai_block(self):
        """Every PUA code point must resolve to a standard Thai character (U+0E00–U+0E7F)."""
        from thai_utils import _THAI_PUA_MAP
        for pua_cp, replacement in _THAI_PUA_MAP.items():
            for ch in replacement:
                assert 0x0E00 <= ord(ch) <= 0x0E7F, (
                    f"U+{pua_cp:04X} mapped to U+{ord(ch):04X} which is outside Thai block"
                )

    # ── Real-word Thai examples ────────────────────────────────────────────

    def test_word_with_pua_tone_mark(self):
        """Word containing PUA tone mark is corrected."""
        # ้ stored as U+F70B instead of U+0E49
        garbled  = "กาว"   # กาว with PUA mai tho
        expected = "ก้าว"
        assert fix_thai_order(garbled) == expected

    def test_word_already_correct(self):
        """Standard Thai text passes through unchanged."""
        word = "สวัสดี"
        assert fix_thai_order(word) == word

    def test_mixed_thai_english(self):
        """Mixed Thai+English text: only PUA chars are replaced."""
        text = "Hello กาว World"
        assert fix_thai_order(text) == "Hello ก้าว World"

    def test_numbers_and_punctuation_unchanged(self):
        """Numbers and punctuation are not affected."""
        text = "1,234.56 (บาท)"
        assert fix_thai_order(text) == text

    # ── Edge cases ────────────────────────────────────────────────────────

    def test_empty_string(self):
        """Empty string returns empty string (no crash)."""
        assert fix_thai_order("") == ""

    def test_none_equivalent(self):
        """Single space passes through."""
        assert fix_thai_order(" ") == " "

    def test_multiple_pua_chars(self):
        """Multiple PUA characters in one string are all replaced."""
        text = ""
        result = fix_thai_order(text)
        assert "" not in result
        assert "" not in result
        assert "" not in result

    def test_no_pua_chars_remain_after_fix(self):
        """After fix, no PUA characters (U+F700–U+F71B) remain."""
        from thai_utils import _THAI_PUA_MAP
        text = "".join(chr(cp) for cp in _THAI_PUA_MAP)
        result = fix_thai_order(text)
        for cp in _THAI_PUA_MAP:
            assert chr(cp) not in result, f"U+{cp:04X} still present after fix"


class TestFontCmapGarbling:
    """
    Tests for the font-CMap garbling recovery in fix_thai_order (Step 3).

    Some Thai PDFs use composite glyphs whose ToUnicode CMap omits
    sara-uu (ู U+0E39) or do-dek (ด U+0E14), producing invalid sequences.
    Two targeted patterns are corrected:
      1. ผ + ้ + consonant/leading-vowel  →  ผู้ + ...
      2. ไ + ้  →  ได้
    """

    # ── Pattern 1: missing sara-uu after pho-phueng ───────────────────────

    def test_pho_mai_tho_before_consonant_gets_sara_uu(self):
        """ผ้ท… should become ผู้ท… (missing ู recovered)."""
        assert fix_thai_order("ผ้ที่เกี่ยวข้อง") == "ผู้ที่เกี่ยวข้อง"

    def test_pho_mai_tho_before_second_consonant(self):
        """ผ้ป… should become ผู้ป… (evaluator / BPO label)."""
        assert fix_thai_order("ผ้ประเมิน") == "ผู้ประเมิน"

    def test_pho_mai_tho_before_leading_vowel(self):
        """ผ้เ… should become ผู้เ… (sara-e as leading vowel)."""
        assert fix_thai_order("ผ้เข้ารับ") == "ผู้เข้ารับ"

    def test_pho_mai_tho_before_sara_aa_unchanged(self):
        """ผ้า (fabric) must NOT be changed to ผู้า — า is a valid suffix."""
        assert fix_thai_order("ผ้า") == "ผ้า"

    def test_pho_mai_tho_in_fabric_word_unchanged(self):
        """ผ้าไหม (silk) must pass through unchanged."""
        assert fix_thai_order("ผ้าไหม") == "ผ้าไหม"

    def test_already_correct_pho_sara_uu_unchanged(self):
        """ผู้ (already has ู) must not be double-fixed."""
        assert fix_thai_order("ผู้ที่เกี่ยวข้อง") == "ผู้ที่เกี่ยวข้อง"

    # ── Pattern 2: missing do-dek in ได้ ──────────────────────────────────

    def test_sara_ai_maimalai_with_mai_tho_becomes_dai(self):
        """ไ้ (impossible in Thai) is always garbled ได้."""
        assert fix_thai_order("ไ้ ข้อมูล") == "ได้ ข้อมูล"

    def test_sara_ai_maimalai_alone_becomes_dai(self):
        """ไ้ alone → ได้."""
        assert fix_thai_order("ไ้") == "ได้"

    def test_sara_ai_in_word_sarai_unchanged(self):
        """ไม่ (no/not) has no tone mark on ไ — must not be touched."""
        assert fix_thai_order("ไม่") == "ไม่"

    def test_sara_ai_maimalai_in_phai_word_unchanged(self):
        """ไป (to go) — ไ followed by consonant, no tone mark on ไ."""
        assert fix_thai_order("ไป") == "ไป"

    # ── Combined / integration ────────────────────────────────────────────

    def test_both_patterns_in_one_string(self):
        """Both patterns fixed in a single string."""
        garbled  = "ผ้ที่ไ้รับ"    # garbled "ผู้ที่ได้รับ"
        expected = "ผู้ที่ได้รับ"
        assert fix_thai_order(garbled) == expected


class TestSaraIIEncoding:
    """
    Tests for multi-component sara-ii (ี U+0E35) recovery.

    Some older Thai PDFs (EGAT/HTE style) encode sara-ii above ascending
    consonants as 2–5 separate glyphs.  Patterns handled:
      - ็้ (U+0E47 + U+0E49) → ี  after PUA mapping
      - ิัิ (U+0E34 + U+0E31 + U+0E34) → ี
      - ิิ  (U+0E34 + U+0E34) → ี
      - ีํ  (sara-ii + nikhahit) → ี  (drop spurious nikhahit)
      - Orphan tone marks after space → removed
    """

    # ── Component collapse ────────────────────────────────────────────────

    def test_mai_taikhu_mai_tho_becomes_sara_ii(self):
        """็้ after PUA mapping → ี."""
        # Simulate PUA-translated result: ป + ็ + ้ → ปี
        garbled = "ป" + "็" + "้"   # ป็้
        assert fix_thai_order(garbled) == "ปี"

    def test_sara_i_sara_a_sara_i_becomes_sara_ii(self):
        """ิ + ั + ิ → ี (3-component encoding)."""
        garbled = "ป" + "ิ" + "ั" + "ิ" + "ไป"   # ปิัิไป
        assert fix_thai_order(garbled) == "ปีไป"

    def test_double_sara_i_becomes_sara_ii(self):
        """ิิ → ี (2-component encoding)."""
        garbled = "ป" + "ิ" + "ิ"   # ปิิ
        assert fix_thai_order(garbled) == "ปี"

    def test_sara_ii_nikhahit_drops_nikhahit(self):
        """ีํ → ี  (spurious nikhahit from split encoding dropped)."""
        garbled = "ปี" + "ํ"    # ปี + nikhahit
        assert fix_thai_order(garbled) == "ปี"

    # ── Orphan tone marks after space ─────────────────────────────────────

    def test_orphan_tone_after_space_removed(self):
        """Tone mark immediately after space has no base consonant → removed."""
        garbled = "ปี " + "่้" + "ปีไป"   # ปี ่้ปีไป
        assert fix_thai_order(garbled) == "ปี ปีไป"

    def test_orphan_nikhahit_after_space_removed(self):
        """Nikhahit immediately after space → removed."""
        garbled = "ปี " + "ํ่้" + " ปีไป"  # ปี ํ่้ ปีไป
        assert fix_thai_order(garbled) == "ปี ปีไป"

    def test_double_space_collapsed(self):
        """Multiple consecutive spaces collapsed to one (side-effect of orphan removal)."""
        assert fix_thai_order("ปี  ปีไป") == "ปี ปีไป"

    # ── Integration: split-line sara-ii simulation ────────────────────────

    def test_split_line_sara_ii_hte04_pattern(self):
        """
        Full pipeline for HTE_04-style encoding where sara-ii is split across
        rawdict lines and _join_cell_lines inserts spaces between PUA segments.

        Raw (before any processing):
          ป + F712 + F70B + SPACE + U+0E4D + F70A + F70B + SPACE + ปิัิไป
        Expected after fix_thai_order:
          ปี ปีไป
        """
        raw = (
            "ป"          # ป + PUA_F712 + PUA_F70B
            " "                            # space from _join_cell_lines
            "ํ"          # ํ(nikhahit) + PUA_F70A + PUA_F70B
            " "                            # space from _join_cell_lines
            "ปิัิ"    # ป + ิ + ั + ิ  (2nd sara-ii encoding)
            "ไป"                 # ไป
        )
        assert fix_thai_order(raw) == "ปี ปีไป"

    def test_valid_thai_unchanged(self):
        """Standard Thai with sara-ii must not be modified."""
        assert fix_thai_order("ปีไป") == "ปีไป"
        assert fix_thai_order("ปีที่แล้ว") == "ปีที่แล้ว"
        assert fix_thai_order("เป็น") == "เป็น"
        assert fix_thai_order("ไม่") == "ไม่"


class TestSaraAmRecomposition:
    """
    Tests for sara-am (ำ U+0E33) recomposition.

    Many Thai PDFs encode ำ as the decomposed sequence nikhahit (ํ U+0E4D) +
    sara-aa (า U+0E32).  NFC does not recompose this, so fix_thai_order must.
    Discovered in the EGAT ERP-HR source PDFs (ทํางาน, สํานัก, กําลัง, …).
    """

    def test_thamngan_recomposed(self):
        """ทํางาน (decomposed) → ทำงาน (composed sara-am)."""
        garbled = "ท" + "ํ" + "า" + "งาน"   # ท + ํ + า + งาน
        assert fix_thai_order(garbled) == "ทำงาน"

    def test_samnak_recomposed(self):
        """สํานัก → สำนัก."""
        assert fix_thai_order("สํานัก") == "สำนัก"

    def test_kamlang_recomposed(self):
        """กําลัง → กำลัง."""
        assert fix_thai_order("กําลัง") == "กำลัง"

    def test_kham_athibai_recomposed(self):
        """คําอธิบาย → คำอธิบาย."""
        assert fix_thai_order("คําอธิบาย") == "คำอธิบาย"

    def test_no_decomposed_sara_am_remains(self):
        """No decomposed sara-am (ํ followed by า) survives the fix."""
        result = fix_thai_order("จัดทําแผน")  # จัดทําแผน → จัดทำแผน
        assert "ํา" not in result
        assert result == "จัดทำแผน"

    def test_already_composed_sara_am_unchanged(self):
        """Correct precomposed ำ (U+0E33) passes through untouched."""
        assert fix_thai_order("ทำงาน") == "ทำงาน"

    def test_standalone_nikhahit_not_followed_by_sara_aa_unchanged(self):
        """A nikhahit NOT followed by sara-aa is left alone (no false merge)."""
        # ก + ํ + ข : ํ is not followed by า, so it must not be merged away
        assert "ํ" in fix_thai_order("ก" + "ํ" + "ข")


class TestFixThaiRow:
    """Tests for fix_thai_row (applies fix_thai_order to every cell)."""

    def test_fixes_all_cells(self):
        row = ["กาว", "Hello", "ข้าว"]
        result = fix_thai_row(row)
        assert result[0] == "ก้าว"
        assert result[1] == "Hello"
        assert result[2] == "ข้าว"

    def test_empty_row(self):
        assert fix_thai_row([]) == []

    def test_row_with_empty_strings(self):
        assert fix_thai_row(["", "", ""]) == ["", "", ""]
