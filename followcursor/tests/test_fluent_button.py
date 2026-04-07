"""
Tests for FluentButton and FluentTabBar animated components.

Tests instantiation, property access, and animation setup without requiring
a running Qt event loop.
"""

import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEasingCurve
from app.fluent_button import FluentButton
from app.fluent_tab_bar import FluentTabBar
from app import tokens as T


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for Qt widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class TestFluentButton:
    """Test FluentButton hover animation functionality."""

    def test_instantiates_without_errors(self, qapp):
        """FluentButton should instantiate without errors."""
        button = FluentButton("Test Button")
        assert button is not None
        assert button.text() == "Test Button"

    def test_hover_opacity_property_exists(self, qapp):
        """FluentButton should expose hover_opacity as a Q_PROPERTY."""
        button = FluentButton()
        # Property should be readable
        assert hasattr(button, "hover_opacity")
        assert button.hover_opacity == 0.0

    def test_hover_opacity_is_settable(self, qapp):
        """hover_opacity property should be writable and trigger update."""
        button = FluentButton()
        button.hover_opacity = 0.5
        assert button.hover_opacity == 0.5
        button.hover_opacity = 1.0
        assert button.hover_opacity == 1.0

    def test_hover_animation_duration(self, qapp):
        """Hover animation should use DURATION_FAST (150ms) with OutCubic easing."""
        button = FluentButton()
        assert button._hover_anim.duration() == T.DURATION_FAST
        assert button._hover_anim.easingCurve().type() == QEasingCurve.Type.OutCubic

    def test_initial_state(self, qapp):
        """FluentButton should initialize with no hover or press state."""
        button = FluentButton()
        assert button._hover_opacity == 0.0
        assert button._pressed is False


class TestFluentTabBar:
    """Test FluentTabBar hover animation functionality."""

    def test_instantiates_without_errors(self, qapp):
        """FluentTabBar should instantiate without errors."""
        tab_bar = FluentTabBar()
        assert tab_bar is not None

    def test_hover_opacity_property_exists(self, qapp):
        """FluentTabBar should expose hover_opacity as a Q_PROPERTY."""
        tab_bar = FluentTabBar()
        assert hasattr(tab_bar, "hover_opacity")
        assert tab_bar.hover_opacity == 0.0

    def test_hover_opacity_is_settable(self, qapp):
        """hover_opacity property should be writable and trigger update."""
        tab_bar = FluentTabBar()
        tab_bar.hover_opacity = 0.5
        assert tab_bar.hover_opacity == 0.5
        tab_bar.hover_opacity = 1.0
        assert tab_bar.hover_opacity == 1.0

    def test_hover_animation_duration(self, qapp):
        """Hover animation should use DURATION_FAST (150ms) with OutCubic easing."""
        tab_bar = FluentTabBar()
        assert tab_bar._hover_anim.duration() == T.DURATION_FAST
        assert tab_bar._hover_anim.easingCurve().type() == QEasingCurve.Type.OutCubic

    def test_initial_state(self, qapp):
        """FluentTabBar should initialize with no hover or press state."""
        tab_bar = FluentTabBar()
        assert tab_bar._hover_opacity == 0.0
        assert tab_bar._hover_tab == -1
        assert tab_bar._pressed_tab == -1

    def test_mouse_tracking_enabled(self, qapp):
        """FluentTabBar should have mouse tracking enabled to detect hover."""
        tab_bar = FluentTabBar()
        assert tab_bar.hasMouseTracking() is True
