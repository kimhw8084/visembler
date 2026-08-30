from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from company_ui.version import FRAMEWORK_VERSION

GUIDE_NAMES = (
    'AI_RULES.md','COMPONENT_CATALOG.md','LAYOUT_RULES.md','APP_PATTERNS.md','RECIPES.md',
    'ANTI_PATTERNS.md','ICON_CATALOG.md','VISUAL_RESOURCE_GUIDE.md','COMPANY_ENVIRONMENT.md',
    'TROUBLESHOOTING.md','RUNTIME_COMPATIBILITY_GUIDE.md','PERFORMANCE_GUIDE.md','PRODUCTION_COMPLETION_GUIDE.md','COMPANY_CERTIFICATION_CHECKLIST.md','GOLD_PROMOTION_HARNESS.md','ZERO_STOCK_NICEGUI_VISUAL_LAWS.md','DESIGN_CONSTITUTION_V1_6.md','V17_PRODUCT_CONSTITUTION.md','V17_FINAL_CERTIFICATION_AND_DEPLOYMENT.md','V171_VISUAL_INTERACTION_HOTFIX.md','DESIGN_CONSTITUTION_V1_5.md','LIVE_CERTIFICATION_GUIDE.md','MAC_LIVE_CERTIFICATION_GUIDE.md','PUBLIC_API_INDEX.md','VALIDATOR_RULES.md','AI_QUICKSTART.md',
)


def read_ai_guide(name: str) -> str:
    if name != 'AGENTS.md' and name not in GUIDE_NAMES:
        raise KeyError(f'Unknown AI guide {name!r}; allowed: AGENTS.md, {", ".join(GUIDE_NAMES)}')
    return files('company_ui.ai').joinpath('guides', name).read_text(encoding='utf-8')


def install_ai_materials(destination: str | Path, *, overwrite: bool = False) -> tuple[Path, ...]:
    """Install the agent contract into an application workspace.

    AGENTS.md is placed at the workspace root; detailed guides are placed under
    docs/company_ui/. Machine-readable construction/catalog JSON is copied to
    .company_ui/ so coding agents can inspect it without importing Python.
    """
    dest = Path(destination)
    docs = dest / 'docs' / 'company_ui'
    meta = dest / '.company_ui'
    docs.mkdir(parents=True, exist_ok=True)
    meta.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    def write(target: Path, content: str) -> None:
        if target.exists() and not overwrite:
            return
        target.write_text(content, encoding='utf-8')
        written.append(target)

    write(dest/'AGENTS.md', read_ai_guide('AGENTS.md'))
    for name in GUIDE_NAMES:
        write(docs/name, read_ai_guide(name))
    package = files('company_ui.ai')
    write(meta/'construction_manifest.json', package.joinpath('construction_manifest.json').read_text(encoding='utf-8'))
    write(meta/'framework_catalog.json', package.joinpath('framework_catalog.json').read_text(encoding='utf-8'))
    write(meta/'install_manifest.json', json.dumps({
        'framework': 'company-ui', 'framework_version': FRAMEWORK_VERSION,
        'generated_files': [str(p.relative_to(dest)) for p in written],
    }, indent=2, sort_keys=True) + '\n')
    return tuple(written)
