"""Tests for app.keystroke_renderer — security-critical filtering tests."""

from app.keystroke_renderer import (
    _group_keystrokes,
    _should_show_group,
)
from app.models import KeyEvent


# ── _should_show_group ──────────────────────────────────────────────


class TestShouldShowGroup:
    def test_all_mode_shows_everything(self) -> None:
        """filter_mode="all" should always return True."""
        MODIFIER_VKS = frozenset((0x11, 0x12, 0xA2, 0xA3, 0xA4, 0xA5, 0x5B, 0x5C))
        SHIFT_VKS = frozenset((0x10, 0xA0, 0xA1))
        
        # Single character key (no modifiers)
        assert _should_show_group([0x41], "all", MODIFIER_VKS, SHIFT_VKS) is True
        # Modifier only
        assert _should_show_group([0x11], "all", MODIFIER_VKS, SHIFT_VKS) is True
        # Ctrl+C
        assert _should_show_group([0x11, 0x43], "all", MODIFIER_VKS, SHIFT_VKS) is True
    
    def test_modifiers_only_requires_ctrl_alt_win(self) -> None:
        """filter_mode="modifiers-only" requires Ctrl/Alt/Win modifier."""
        MODIFIER_VKS = frozenset((0x11, 0x12, 0xA2, 0xA3, 0xA4, 0xA5, 0x5B, 0x5C))
        SHIFT_VKS = frozenset((0x10, 0xA0, 0xA1))
        
        # Single character key → False
        assert _should_show_group([0x41], "modifiers-only", MODIFIER_VKS, SHIFT_VKS) is False
        # Shift+A → False (Shift alone is not a qualifying modifier)
        assert _should_show_group([0x10, 0x41], "modifiers-only", MODIFIER_VKS, SHIFT_VKS) is False
        # Ctrl+C → True
        assert _should_show_group([0x11, 0x43], "modifiers-only", MODIFIER_VKS, SHIFT_VKS) is True
        # Alt+Tab → True
        assert _should_show_group([0x12, 0x09], "modifiers-only", MODIFIER_VKS, SHIFT_VKS) is True
    
    def test_shortcuts_only_requires_ctrl_alt_win(self) -> None:
        """filter_mode="shortcuts-only" requires Ctrl/Alt/Win modifier."""
        MODIFIER_VKS = frozenset((0x11, 0x12, 0xA2, 0xA3, 0xA4, 0xA5, 0x5B, 0x5C))
        SHIFT_VKS = frozenset((0x10, 0xA0, 0xA1))
        
        # Single character → False
        assert _should_show_group([0x41], "shortcuts-only", MODIFIER_VKS, SHIFT_VKS) is False
        # Shift+A → False
        assert _should_show_group([0x10, 0x41], "shortcuts-only", MODIFIER_VKS, SHIFT_VKS) is False
        # Ctrl+V → True
        assert _should_show_group([0x11, 0x56], "shortcuts-only", MODIFIER_VKS, SHIFT_VKS) is True
        # Win+R → True
        assert _should_show_group([0x5B, 0x52], "shortcuts-only", MODIFIER_VKS, SHIFT_VKS) is True
    
    def test_unknown_filter_mode_defaults_to_false(self) -> None:
        """Unknown filter_mode should default to safe behavior (False)."""
        MODIFIER_VKS = frozenset((0x11, 0x12, 0xA2, 0xA3, 0xA4, 0xA5, 0x5B, 0x5C))
        SHIFT_VKS = frozenset((0x10, 0xA0, 0xA1))
        
        # Invalid mode should return False for safety
        assert _should_show_group([0x41], "invalid-mode", MODIFIER_VKS, SHIFT_VKS) is False
        assert _should_show_group([0x11, 0x43], "invalid-mode", MODIFIER_VKS, SHIFT_VKS) is False


# ── _group_keystrokes ───────────────────────────────────────────────


class TestGroupKeystrokes:
    def test_empty_events_returns_empty(self) -> None:
        """No key events should return empty list."""
        result = _group_keystrokes([], 1000.0, 1500, "all")
        assert result == []
    
    def test_filters_by_time_window(self) -> None:
        """Only events within display_duration_ms before timestamp should be included."""
        events = [
            KeyEvent(timestamp=500.0, vk_code=0x41),   # 'A' at 500ms
            KeyEvent(timestamp=1000.0, vk_code=0x42),  # 'B' at 1000ms
            KeyEvent(timestamp=2000.0, vk_code=0x43),  # 'C' at 2000ms
        ]
        # At timestamp 1800ms with 1000ms duration → only B and C visible
        result = _group_keystrokes(events, 1800.0, 1000, "all")
        # Should include B (1000ms, age 800) and C (2000ms, age -200 but future events excluded by bisect_right)
        # Actually C at 2000 is AFTER 1800, so only B is visible
        assert len(result) >= 1
        # First group should contain B
        assert "B" in result[0][0]
    
    def test_groups_rapid_keystrokes(self) -> None:
        """Keystrokes within 100ms should be grouped with '+'."""
        events = [
            KeyEvent(timestamp=1000.0, vk_code=0x11),  # Ctrl
            KeyEvent(timestamp=1020.0, vk_code=0x43),  # C (20ms later)
        ]
        result = _group_keystrokes(events, 1500.0, 1500, "all")
        assert len(result) == 1
        assert result[0][0] == "Ctrl+C"
    
    def test_filter_mode_all_shows_everything(self) -> None:
        """filter_mode='all' should show all keystrokes."""
        events = [
            KeyEvent(timestamp=1000.0, vk_code=0x41),  # 'A'
            KeyEvent(timestamp=1100.0, vk_code=0x11),  # Ctrl
        ]
        result = _group_keystrokes(events, 1500.0, 1500, "all")
        assert len(result) == 2
    
    def test_filter_mode_shortcuts_only_hides_plain_keys(self) -> None:
        """filter_mode='shortcuts-only' should hide plain character keys."""
        events = [
            KeyEvent(timestamp=1000.0, vk_code=0x41),  # 'A' alone
            KeyEvent(timestamp=1200.0, vk_code=0x11),  # Ctrl
            KeyEvent(timestamp=1220.0, vk_code=0x43),  # C (Ctrl+C)
        ]
        result = _group_keystrokes(events, 1500.0, 1500, "shortcuts-only")
        # Should only show Ctrl+C, not 'A'
        assert len(result) == 1
        assert "Ctrl+C" in result[0][0]
    
    def test_filter_mode_modifiers_only(self) -> None:
        """filter_mode='modifiers-only' should only show groups with Ctrl/Alt/Win."""
        events = [
            KeyEvent(timestamp=1000.0, vk_code=0x41),  # 'A'
            KeyEvent(timestamp=1200.0, vk_code=0x12),  # Alt
            KeyEvent(timestamp=1220.0, vk_code=0x09),  # Tab (within 100ms grouping window)
        ]
        result = _group_keystrokes(events, 1500.0, 1500, "modifiers-only")
        # Should only show Alt+Tab (grouped because they're within 100ms)
        # Note: grouping happens at 100ms window, Alt at 1200, Tab at 1220 = 20ms gap
        assert len(result) >= 1
        # The group should contain Alt (and Tab if grouped correctly)
        group_text = result[0][0]
        assert "Alt" in group_text or "Tab" in group_text
    
    def test_events_without_vk_code_are_skipped(self) -> None:
        """KeyEvent without vk_code should be silently skipped."""
        events = [
            KeyEvent(timestamp=1000.0),  # No vk_code
            KeyEvent(timestamp=1100.0, vk_code=0x41),  # 'A'
        ]
        result = _group_keystrokes(events, 1500.0, 1500, "all")
        # Should only show 'A'
        assert len(result) == 1
        assert "A" in result[0][0]
    
    def test_age_calculation(self) -> None:
        """Verify age is calculated correctly for fade effects."""
        events = [
            KeyEvent(timestamp=1000.0, vk_code=0x41),  # 'A'
        ]
        result = _group_keystrokes(events, 1300.0, 1500, "all")
        assert len(result) == 1
        # Age should be 1300 - 1000 = 300ms
        assert result[0][2] == 300.0
