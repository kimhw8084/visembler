"""The pinned runtime's default color must not override Company intents."""
import pytest

from company_ui import ActionButton, Button, ButtonIntent, DangerConfirmDialog, FormDialog


@pytest.mark.parametrize('component', [Button, ActionButton])
@pytest.mark.parametrize('intent', list(ButtonIntent))
def test_company_intent_has_no_runtime_color_override(component, intent):
    button = component('Intent action', intent=intent)
    assert 'color' not in button.element._props
    assert f'cui-button--{intent.value}' in button.element._classes


@pytest.mark.parametrize('component', [FormDialog, DangerConfirmDialog])
def test_dialog_action_preserves_company_intent(component):
    dialog = component('Intent confirmation', primary_label='Commit')
    assert 'color' not in dialog.primary_button._props
    intent = 'danger' if component is DangerConfirmDialog else 'primary'
    assert f'cui-button--{intent}' in dialog.primary_button._classes
