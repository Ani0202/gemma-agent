"""Stdlib scripted OpenAI server. Script: JSON list of assistant messages or completions."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time


def make_server(script, host='127.0.0.1', port=0):
    responses = json.loads(Path(script).read_text())
    if not isinstance(responses, list) or not responses:
        raise ValueError('Script must be a nonempty JSON array')
    lock = threading.Lock()
    position = 0

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send_json(self, status, payload):
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path.rstrip('/') == '/v1/models':
                self.send_json(200, dict(object='list', data=[dict(id='gemma-4-e4b-it-qat-w4a16-ct',
                                                                 object='model', owned_by='stub')]))
            else:
                self.send_json(404, dict(error='Unknown route'))

        def do_POST(self):
            nonlocal position
            if self.path.rstrip('/') != '/v1/chat/completions':
                self.send_json(404, dict(error='Unknown route'))
                return
            request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if request.get('stream'):
                self.send_json(400, dict(error='Stub supports non-streaming requests only'))
                return
            with lock:
                if position >= len(responses):
                    self.send_json(409, dict(error='Script exhausted'))
                    return
                entry = responses[position]
                position += 1
                index = position
            if 'choices' in entry:
                payload = entry
            else:
                message = dict(role='assistant', **{k: v for k, v in entry.items() if k != 'role'})
                payload = dict(choices=[dict(index=0, message=message, finish_reason=(
                    'tool_calls' if message.get('tool_calls') else 'stop'))])
            payload = dict(id=f'chatcmpl-stub-{index}', object='chat.completion',
                           created=int(time.time()), model=request.get('model', 'stub'), **payload)
            self.send_json(200, payload)

    return ThreadingHTTPServer((host, port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', required=True, type=Path)
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    with make_server(args.script, port=args.port) as server:
        print(f'http://127.0.0.1:{server.server_port}/v1', flush=True)
        server.serve_forever()


if __name__ == '__main__':
    main()
