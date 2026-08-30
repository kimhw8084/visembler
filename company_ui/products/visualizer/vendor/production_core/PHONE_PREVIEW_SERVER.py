#!/usr/bin/env python3
from __future__ import annotations
import argparse, http.server, socket, sys, threading, webbrowser
from pathlib import Path

ROOT=Path(__file__).resolve().parent
START='APPROVAL_PREVIEW_STANDALONE.html'

def lan_ip():
    s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    try:
        s.connect(('192.0.2.1',80)); return s.getsockname()[0]
    except OSError:
        try:return socket.gethostbyname(socket.gethostname())
        except OSError:return '127.0.0.1'
    finally:s.close()

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw): super().__init__(*a,directory=str(ROOT),**kw)
    def end_headers(self):
        self.send_header('Cache-Control','no-store, max-age=0')
        self.send_header('Pragma','no-cache')
        super().end_headers()
    def log_message(self,fmt,*args): print('[preview]',fmt%args)

def bind_server(port):
    for p in range(port,port+20):
        try:return http.server.ThreadingHTTPServer(('0.0.0.0',p),Handler),p
        except OSError:continue
    raise OSError('No free preview port found')

def main():
    ap=argparse.ArgumentParser(description='Visualizer 97.1 phone approval preview')
    ap.add_argument('--port',type=int,default=8765);ap.add_argument('--no-open',action='store_true');args=ap.parse_args()
    server,port=bind_server(args.port);ip=lan_ip();desktop=f'http://127.0.0.1:{port}/{START}';phone=f'http://{ip}:{port}/{START}'
    print('\nVisualizer 97.1 / 100 — Approval Preview')
    print('='*54)
    print('DESKTOP:',desktop)
    print('PHONE:  ',phone)
    print('\nPhone and computer must be on the same reachable network.')
    print('Press Control-C to stop the preview server.\n')
    if not args.no_open:
        threading.Timer(.5,lambda:webbrowser.open(desktop)).start()
    try:server.serve_forever()
    except KeyboardInterrupt:print('\nPreview server stopped.')
    finally:server.server_close()
if __name__=='__main__':main()
