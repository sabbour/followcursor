"""Tests for source-selection onboarding and keyboard accessibility."""

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QPushButton

from app.main_window import MainWindow
from app.widgets.source_picker import _SourceCard


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_placeholder_has_explicit_source_action(qapp):
    owner = SimpleNamespace(_select_source=lambda: None)

    placeholder = MainWindow._build_placeholder(owner)
    choose_button = placeholder.findChild(QPushButton, "SourceCtaBtn")

    assert choose_button is not None
    assert choose_button.text() == "Choose recording source"
    assert choose_button.accessibleDescription() == "Choose a screen or window to record"


def test_source_card_is_keyboard_focusable_and_named(qapp):
    card = _SourceCard({"name": "Display 1"})

    assert card.focusPolicy() == Qt.FocusPolicy.StrongFocus
    assert card.accessibleName() == "Display 1 capture source"
    assert card.accessibleDescription() == "Not selected"


@pytest.mark.parametrize("key", [Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space])
def test_source_card_keyboard_activation_selects_and_emits(qapp, key):
    card = _SourceCard({"name": "Display 1"})
    activated = []
    card.activated.connect(activated.append)

    card.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier))

    assert card.selected is True
    assert card.accessibleDescription() == "Selected"
    assert activated == [{"name": "Display 1"}]


def test_small_control_radius_matches_design_contract():
    from app import tokens as T

    assert T.RADIUS_SMALL == 6


def test_theme_has_explicit_disabled_sidebar_treatment():
    from app.theme import get_theme

    theme = get_theme(dark=True)
    assert "QToolButton#SidebarBtn:disabled" in theme
    assert "color: #5c5c5c" in theme


class _ActionStub:
    def __init__(self) -> None:
        self.enabled = True
        self.tooltip = ""
        self.icon = None

    def setEnabled(self, enabled: bool) -> None:
        self.enabled = enabled

    def setToolTip(self, tooltip: str) -> None:
        self.tooltip = tooltip

    def setIcon(self, icon) -> None:
        self.icon = icon


class _TitleBarStub:
    def __init__(self) -> None:
        self.export_enabled = True

    def set_export_enabled(self, enabled: bool) -> None:
        self.export_enabled = enabled


@pytest.mark.parametrize("dark_mode", [True, False])
def test_project_actions_remain_disabled_in_both_themes(qapp, dark_mode):
    owner = SimpleNamespace(
        _has_recording=lambda: False,
        _dark_mode=dark_mode,
        _view="record",
        _btn_edit_view=_ActionStub(),
        _btn_save=_ActionStub(),
        _title_bar=_TitleBarStub(),
    )

    MainWindow._sync_project_actions(owner)

    assert owner._btn_edit_view.enabled is False
    assert owner._btn_save.enabled is False
    assert owner._title_bar.export_enabled is False
    assert "Record or open" in owner._btn_edit_view.tooltip
    assert "Record or open" in owner._btn_save.tooltip
    assert owner._btn_edit_view.icon is not None
    assert owner._btn_save.icon is not None