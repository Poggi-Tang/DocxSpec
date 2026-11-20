"""Local model response for the Studio browser regression; accepts a one-paragraph fixture."""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FixtureHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        block = json.loads(request["messages"][-1]["content"])["source_blocks"][0]
        draft = {
            "document": {
                "nodes": [
                    {"id": "review-paragraph", "kind": "paragraph", "text": block["text"]},
                ]
            },
            "data": {},
            "review": [
                {
                    "source_ids": [block["source_id"]],
                    "node_ids": ["review-paragraph"],
                    "decision": "保留原文",
                    "reason": "待确认是否为固定内容",
                    "needs_confirmation": True,
                }
            ],
        }
        body = json.dumps({"choices": [{"message": {"content": json.dumps(draft)}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=4223)
    with ThreadingHTTPServer(("127.0.0.1", parser.parse_args().port), FixtureHandler) as server:
        server.serve_forever()
