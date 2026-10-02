import pytest

from company_ui.products.visualizer.presentation import ReportCopy


@pytest.mark.parametrize('value', [
    '<img src=x onerror="window.copyExecuted=true"> **not Markdown** & data',
    'Reference < Affected > control · "quoted"\nSecond line',
])
def test_report_copy_remains_plain_text_on_initial_render_and_update(value):
    from html import escape

    copy = ReportCopy(value, tag='h3')
    assert copy.element.content == escape(value)
    assert copy.element._props['sanitize'] is True
    assert copy.element._props['tag'] == 'h3'
    copy.set_text('Changed: ' + value)
    assert copy.element.content == escape('Changed: ' + value)
    assert copy.element._props['sanitize'] is True


def test_report_copy_rejects_active_or_control_semantics():
    with pytest.raises(ValueError, match='Unsupported report copy semantics'):
        ReportCopy('Report title', tag='script')
