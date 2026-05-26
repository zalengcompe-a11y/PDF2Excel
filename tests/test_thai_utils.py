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

    def test_pua_f710_mai_taikhu(self):
        """U+F710 → ็ U+0E47 mai taikhu (ascender form)"""
        assert fix_thai_order("") == "็"

    def test_pua_f70e_thanthakat(self):
        """U+F70E → ์ U+0E4C thanthakat"""
        assert fix_thai_order("") == "์"

    def test_pua_f712_mai_ek_ascender(self):
        """U+F712 → ่ U+0E48 mai ek (ascender form)"""
        assert fix_thai_order("") == "่"

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
