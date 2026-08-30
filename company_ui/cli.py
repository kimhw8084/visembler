from __future__ import annotations
import argparse,sys
from pathlib import Path


def main()->int:
    p=argparse.ArgumentParser(prog='company-ui',description='Company UI framework tools')
    sub=p.add_subparsers(dest='command',required=True)
    d=sub.add_parser('doctor',help='Run platform/runtime/browser preflight');d.add_argument('--port',type=int,default=8080);d.add_argument('--require-edge',action='store_true');d.add_argument('--no-require-browser',action='store_true',help='Do not require Chrome/Chromium');d.add_argument('--runtime-only',action='store_true',help='Production-runtime profile: Playwright/Pillow are optional');d.add_argument('--ignore-port',action='store_true',help='Do not require the requested port to be free');d.add_argument('--format',choices=('text','json'),default='text')
    l=sub.add_parser('lab',help='Run the live reference/certification laboratory');l.add_argument('--host',default='127.0.0.1');l.add_argument('--port',type=int,default=8080);l.add_argument('--show',action='store_true')
    c=sub.add_parser('certify',help='Run live runtime/browser/geometry certification');c.add_argument('--output',type=Path,default=Path('certification_output'));c.add_argument('--baseline',type=Path,default=Path('visual_baseline'));c.add_argument('--root',type=Path,default=Path.cwd());c.add_argument('--port',type=int,default=8080);c.add_argument('--exhaustive',action='store_true');c.add_argument('--no-edge',action='store_true');c.add_argument('--require-edge',action='store_true');c.add_argument('--require-baseline',action='store_true');c.add_argument('--format',choices=('text','json'),default='text')
    a=sub.add_parser('approve-baseline',help='Approve the last passing screenshot set after human review');a.add_argument('--output',type=Path,default=Path('certification_output'));a.add_argument('--baseline',type=Path,default=Path('visual_baseline'));a.add_argument('--force',action='store_true')
    rc=sub.add_parser('runtime-contract',help='Verify exact installed NiceGUI API compatibility');rc.add_argument('--format',choices=('text','json'),default='text')
    rs=sub.add_parser('runtime-smoke',help='Start real NiceGUI server and smoke every live route without a browser');rs.add_argument('--output',type=Path,default=Path('certification_output/runtime_smoke'));rs.add_argument('--port',type=int,default=0);rs.add_argument('--format',choices=('text','json'),default='text')
    args=p.parse_args()
    if args.command=='doctor':
        from company_ui.certification.live_preflight import main as cmd
        argv=['company-ui doctor','--port',str(args.port),'--format',args.format]+(['--require-edge'] if args.require_edge else [])+(['--no-require-browser'] if args.no_require_browser else [])+(['--runtime-only'] if args.runtime_only else [])+(['--ignore-port'] if args.ignore_port else [])
    elif args.command=='lab':
        from company_ui.certification.live_lab_cli import main as cmd
        argv=['company-ui lab','--host',args.host,'--port',str(args.port)]+(['--show'] if args.show else [])
    elif args.command=='runtime-contract':
        from company_ui.certification.nicegui_runtime_contract import main as cmd
        argv=['company-ui runtime-contract','--format',args.format]
    elif args.command=='runtime-smoke':
        from company_ui.certification.runtime_smoke import main as cmd
        argv=['company-ui runtime-smoke','--output',str(args.output),'--port',str(args.port),'--format',args.format]
    elif args.command=='certify':
        from company_ui.certification.live_certify import main as cmd
        argv=['company-ui certify','--output',str(args.output),'--baseline',str(args.baseline),'--root',str(args.root),'--port',str(args.port),'--format',args.format]
        if args.exhaustive:argv.append('--exhaustive')
        if args.no_edge:argv.append('--no-edge')
        if args.require_edge:argv.append('--require-edge')
        if args.require_baseline:argv.append('--require-baseline')
    else:
        from company_ui.certification.live_baseline import main as cmd
        argv=['company-ui approve-baseline','--output',str(args.output),'--baseline',str(args.baseline)]+(['--force'] if args.force else [])
    old=sys.argv;sys.argv=argv
    try:return cmd()
    finally:sys.argv=old

if __name__=='__main__':raise SystemExit(main())
