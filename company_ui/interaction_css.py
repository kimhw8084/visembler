from company_ui.forms.css import build_form_css
from company_ui.filters.css import build_filter_css
from company_ui.feedback.css import build_feedback_css
from company_ui.overlays.css import build_overlay_css


def build_interaction_css() -> str:
    return '\n'.join((build_form_css(), build_filter_css(), build_feedback_css(), build_overlay_css()))

__all__ = ['build_interaction_css']
