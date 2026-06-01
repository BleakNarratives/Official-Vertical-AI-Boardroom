#!/usr/bin/env python3
"""
Boardroom Bridge -- local API server
Connects Three.js frontend to vertical_ai CLI backend
Run: python3 boardroom_bridge.py
Then open boardroom_3d.html in browser
"""
import json, os, subprocess, sys, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

PORT = 8767
BASE = os.path.dirname(os.path.abspath(__file__))

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass  # quiet

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        if path == '/sessions':
            # List all saved session JSONs
            sessions = []
            for f in os.listdir(BASE):
                if f.startswith('vai_output_') and f.endswith('.json'):
                    try:
                        with open(os.path.join(BASE, f)) as fp:
                            d = json.load(fp)
                        sessions.append({
                            'file': f,
                            'session': d.get('session_id',''),
                            'label': d.get('context',{}).get('label',''),
                            'verdict': d.get('boardroom',{}).get('synthesis',{}).get('verdict',''),
                            'champion': d.get('champion',{}).get('name',''),
                        })
                    except: pass
            self._json(sessions)

        elif path.startswith('/session/'):
            sid = path.split('/')[-1]
            fname = f'vai_output_{sid}.json'
            fpath = os.path.join(BASE, fname)
            if os.path.exists(fpath):
                with open(fpath) as f:
                    self._json(json.load(f))
            else:
                self._json({'error': 'not found'}, 404)

        elif path == '/status':
            self._json({'status': 'online', 'port': PORT})

        else:
            self._json({'error': 'not found'}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        if path == '/convene':
            brief = body.get('brief', '')
            vertical = body.get('vertical', '')
            rounds = body.get('rounds', 1)
            tracks = body.get('tracks', 2)
            iterations = body.get('iterations', 2)

            if not brief:
                self._json({'error': 'no brief'}, 400)
                return

            # Run vertical_ai.py as subprocess
            cmd = [sys.executable, os.path.join(BASE, 'vertical_ai.py'),
                   '--text', brief,
                   '--rounds', str(rounds),
                   '--tracks', str(tracks),
                   '--iterations', str(iterations),
                   '--no-neo4j',
                   '--outreach']

            if vertical:
                cmd += ['--vertical', vertical]

            try:
                result = subprocess.run(
                    cmd,
                    cwd=BASE,
                    capture_output=True,
                    text=True,
                    timeout=120
                )

                # Find the output JSON
                output_file = None
                for line in result.stdout.split('\n'):
                    if line.startswith('  Output:'):
                        output_file = line.split('Output:')[-1].strip()
                        break

                if output_file:
                    fpath = os.path.join(BASE, output_file)
                    if os.path.exists(fpath):
                        with open(fpath) as f:
                            data = json.load(f)
                        data['_stdout'] = result.stdout[-2000:]
                        self._json(data)
                        return

                self._json({
                    'error': 'no output file',
                    'stdout': result.stdout[-1000:],
                    'stderr': result.stderr[-500:]
                }, 500)

            except subprocess.TimeoutExpired:
                self._json({'error': 'timeout'}, 504)
            except Exception as e:
                self._json({'error': str(e)}, 500)

        elif path == '/upload':
            content = body.get('content', '')
            filename = body.get('filename', 'upload.txt')
            fpath = os.path.join(BASE, 'uploads', filename)
            os.makedirs(os.path.join(BASE, 'uploads'), exist_ok=True)
            with open(fpath, 'w') as f:
                f.write(content)
            self._json({'saved': fpath, 'chars': len(content)})

        else:
            self._json({'error': 'not found'}, 404)

    def _json(self, data, code=200):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

if __name__ == '__main__':
    server = HTTPServer(('127.0.0.1', PORT), Handler)
    print(f'[Bridge] Boardroom bridge running on http://127.0.0.1:{PORT}')
    print(f'[Bridge] Open boardroom_3d.html in browser')
    print(f'[Bridge] CLI still works: python vertical_ai.py --text "your idea"')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n[Bridge] Stopped')
