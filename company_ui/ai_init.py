from __future__ import annotations

import argparse
from pathlib import Path
from company_ui.ai.scaffold import install_ai_materials


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description='Install Company UI Gemma/OpenCode guidance into an application workspace.')
    parser.add_argument('path', nargs='?', default='.')
    parser.add_argument('--overwrite', action='store_true')
    args=parser.parse_args(argv)
    written=install_ai_materials(Path(args.path), overwrite=args.overwrite)
    print(f'Company UI AI materials: {len(written)} files written.')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
