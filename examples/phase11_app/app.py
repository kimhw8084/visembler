from company_ui import NiceGUIRuntimeAdapter, RuntimeConfig


def runtime() -> NiceGUIRuntimeAdapter:
    return NiceGUIRuntimeAdapter(RuntimeConfig('Equipment Health'))
