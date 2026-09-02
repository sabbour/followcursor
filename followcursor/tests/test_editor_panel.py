"""Qt-level tests for the editor panel chapter controls."""

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QPlainTextEdit

from app.widgets.editor_panel import EditorPanel


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for Qt widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class TestEditorPanelChapters:
    """Verify the AI chapter controls are wired into the editor panel."""

    def test_generate_chapters_button_emits_signal(self, qapp):
        panel = EditorPanel()
        emitted: list[bool] = []
        panel.generate_chapters_requested.connect(lambda: emitted.append(True))

        panel._btn_generate_chapters.click()

        assert emitted == [True]

    def test_set_ai_busy_disables_ai_chapter_button(self, qapp):
        panel = EditorPanel()

        panel.set_ai_busy(True)
        assert not panel._btn_generate_chapters.isEnabled()
        assert not panel._btn_generate_narration.isEnabled()

        panel.set_ai_busy(False)
        assert panel._btn_generate_chapters.isEnabled()
        assert panel._btn_generate_narration.isEnabled()

    def test_chapter_copy_avoids_removed_features(self, qapp):
        panel = EditorPanel()

        visible_copy = " ".join(
            [
                panel._btn_generate_chapters.toolTip(),
                *[label.text() for label in panel.findChildren(QLabel)],
            ]
        ).lower()

        assert "annotation" not in visible_copy
        assert "keystroke" not in visible_copy


class TestEditorPanelNavigation:
    """Verify the inspector reveals one editing task group at a time."""

    def test_task_tabs_are_ordered_by_primary_workflow(self, qapp):
        panel = EditorPanel()

        assert [panel._tabs.tabText(index) for index in range(panel._tabs.count())] == [
            "Motion",
            "Style",
            "Audio",
        ]
        assert panel._tabs.currentIndex() == 0

    def test_sections_are_grouped_by_editing_task(self, qapp):
        panel = EditorPanel()

        section_titles = []
        for index in range(panel._tabs.count()):
            page = panel._tabs.widget(index)
            section_titles.append(
                {
                    button.text()
                    for button in page.findChildren(type(panel._btn_undo))
                    if button.objectName() == "InspectorSectionHeader"
                }
            )

        assert section_titles == [
            {"SMART ZOOM"},
            {"BACKGROUND", "DEVICE FRAME", "CLICK EFFECTS", "OUTPUT SIZE"},
            {"CHAPTERS", "VOICEOVER"},
        ]

    def test_style_options_start_collapsed(self, qapp):
        panel = EditorPanel()
        style_page = panel._tabs.widget(1)
        section_buttons = [
            button
            for button in style_page.findChildren(type(panel._btn_undo))
            if button.objectName() == "InspectorSectionHeader"
        ]

        assert len(section_buttons) == 4
        assert all(button.property("collapsed") for button in section_buttons)

    def test_style_sections_open_exclusively(self, qapp):
        panel = EditorPanel()
        style_page = panel._tabs.widget(1)
        section_buttons = [
            button
            for button in style_page.findChildren(type(panel._btn_undo))
            if button.objectName() == "InspectorSectionHeader"
        ]

        section_buttons[0].click()
        assert not section_buttons[0].property("collapsed")

        section_buttons[1].click()
        assert section_buttons[0].property("collapsed")
        assert not section_buttons[1].property("collapsed")

    def test_audio_sections_open_exclusively(self, qapp):
        panel = EditorPanel()
        audio_page = panel._tabs.widget(2)
        section_buttons = [
            button
            for button in audio_page.findChildren(type(panel._btn_undo))
            if button.objectName() == "InspectorSectionHeader"
        ]

        assert section_buttons[0].property("collapsed")
        assert not section_buttons[1].property("collapsed")

        section_buttons[0].click()
        assert not section_buttons[0].property("collapsed")
        assert section_buttons[1].property("collapsed")

    def test_status_feedback_is_compact_and_preserves_full_text(self, qapp):
        panel = EditorPanel()
        panel.resize(320, 600)
        panel.show()
        qapp.processEvents()
        message = "Narration is ready. Saved a-very-long-generated-voiceover-script-name.md."

        panel.set_narration_status(message)
        qapp.processEvents()

        assert panel._narration_status.toolTip() == message
        assert panel._narration_status.accessibleName() == message
        assert panel._narration_status.text() != message

        panel.set_voiceover_status("Voiceover ready.")
        assert panel._narration_status.isHidden()
        assert not panel._vo_status.isHidden()


class TestEditorPanelNarrationGuidance:
    """Verify the narration guidance prompt input is wired correctly."""

    def test_guidance_field_exists(self, qapp):
        """The guidance QPlainTextEdit must be present."""
        panel = EditorPanel()
        assert hasattr(panel, "_narration_guidance")
        assert isinstance(panel._narration_guidance, QPlainTextEdit)

    def test_guidance_field_is_optional_by_default(self, qapp):
        """The guidance field starts empty — it is optional."""
        panel = EditorPanel()
        assert panel._narration_guidance.toPlainText() == ""

    def test_generate_narration_emits_guidance_text(self, qapp):
        """Clicking Generate narration emits the current guidance text."""
        panel = EditorPanel()
        emitted: list[tuple[str, str]] = []
        panel.generate_narration_requested.connect(
            lambda voice, guidance: emitted.append((voice, guidance))
        )

        panel._narration_guidance.setPlainText("lead with the time saved")
        panel._btn_generate_narration.click()

        assert len(emitted) == 1
        assert emitted[0][1] == "lead with the time saved"

    def test_generate_narration_emits_empty_guidance_when_blank(self, qapp):
        """Clicking Generate narration with no guidance emits an empty string."""
        panel = EditorPanel()
        emitted: list[tuple[str, str]] = []
        panel.generate_narration_requested.connect(
            lambda voice, guidance: emitted.append((voice, guidance))
        )

        panel._btn_generate_narration.click()

        assert len(emitted) == 1
        assert emitted[0][1] == ""

    def test_guidance_label_copy_signals_optional(self, qapp):
        """The label above the guidance field must include the word 'optional'."""
        panel = EditorPanel()
        label_texts = [lbl.text().lower() for lbl in panel.findChildren(QLabel)]
        assert any("optional" in t for t in label_texts)

    def test_guidance_placeholder_copy_is_not_empty(self, qapp):
        """The placeholder text gives the user a concrete example."""
        panel = EditorPanel()
        placeholder = panel._narration_guidance.placeholderText()
        assert len(placeholder) > 0
