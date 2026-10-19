"""
litrun OpenAI-Compatible REST Server
Serves /v1/chat/completions, /v1/models, /v1/hardware, and /health.
Built with zero required dependencies using standard library ThreadingHTTPServer.
"""

from __future__ import annotations
import json
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from litrun.hardware import probe_hardware
from litrun.governor import poll_governor
from litrun.registry import list_models, get_model

if TYPE_CHECKING:
    from litrun.model import Model


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class LitrunOpenAIHandler(BaseHTTPRequestHandler):
    model_instance: Optional["Model"] = None
    protocol_version = "HTTP/1.1"

    def _send_json(self, status_code: int, data: Any):
        payload = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Connection", "close")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(payload)
        self.close_connection = True

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        if self.path in ["/", "/health"]:
            self._send_json(200, {
                "status": "healthy",
                "litrun_version": "0.1.0",
                "service": "litrun OpenAI-Compatible REST Server",
            })
        elif self.path == "/v1/hardware":
            hw = probe_hardware()
            gov = poll_governor()
            self._send_json(200, {
                "hardware": hw.to_dict(),
                "governor": gov.to_dict(),
            })
        elif self.path == "/v1/models":
            models = list_models()
            data = [
                {
                    "id": m.id,
                    "object": "model",
                    "created": 1700000000,
                    "owned_by": "litrun",
                    "name": m.name,
                    "family": m.family,
                    "default_context": m.default_context,
                }
                for m in models
            ]
            self._send_json(200, {"object": "list", "data": data})
        else:
            self._send_json(404, {"error": {"message": f"Path {self.path} not found"}})

    def do_POST(self):
        if self.path == "/v1/chat/completions":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception as e:
                self._send_json(400, {"error": {"message": f"Invalid JSON payload: {str(e)}"}})
                return

            messages = payload.get("messages", [])
            stream = payload.get("stream", False)
            model_id = payload.get("model", "qwen2.5-0.5b")

            model = LitrunOpenAIHandler.model_instance
            if model is None:
                from litrun.model import Model
                model = Model.load(model_id, allow_mock=True)

            # Build prompt
            prompt_parts = []
            for msg in messages:
                prompt_parts.append(f"{msg.get('role', 'user')}: {msg.get('content', '')}")
            prompt = "\n".join(prompt_parts)

            req_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
            created_ts = int(time.time())

            if stream:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                for chunk in model.stream(prompt):
                    sse_chunk = {
                        "id": req_id,
                        "object": "chat.completion.chunk",
                        "created": created_ts,
                        "model": model.entry.id,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": chunk},
                                "finish_reason": None,
                            }
                        ],
                    }
                    self.wfile.write(f"data: {json.dumps(sse_chunk)}\n\n".encode("utf-8"))
                    self.wfile.flush()

                # Termination chunk
                stop_chunk = {
                    "id": req_id,
                    "object": "chat.completion.chunk",
                    "created": created_ts,
                    "model": model.entry.id,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }
                self.wfile.write(f"data: {json.dumps(stop_chunk)}\n\n".encode("utf-8"))
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
                self.close_connection = True
            else:
                full_response = model.generate(prompt)
                resp = {
                    "id": req_id,
                    "object": "chat.completion",
                    "created": created_ts,
                    "model": model.entry.id,
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": full_response,
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": len(prompt) // 4,
                        "completion_tokens": len(full_response) // 4,
                        "total_tokens": (len(prompt) + len(full_response)) // 4,
                    },
                }
                self._send_json(200, resp)
        else:
            self._send_json(404, {"error": {"message": f"Endpoint {self.path} not found"}})


def start_server(
    model: Optional["Model"] = None,
    host: str = "0.0.0.0",
    port: int = 8080,
    model_id: str = "qwen2.5-0.5b",
) -> None:
    if model is None:
        from litrun.model import Model
        model = Model.load(model_id, allow_mock=True)

    LitrunOpenAIHandler.model_instance = model
    server = ThreadedHTTPServer((host, port), LitrunOpenAIHandler)
    print(f"\n⚡ litrun REST Server active at http://{host}:{port}")
    print(f"   Model: {model.entry.name} ({model.variant.quant})")
    print(f"   OpenAI Endpoint: http://{host}:{port}/v1/chat/completions")
    print(f"   Hardware Telemetry: http://{host}:{port}/v1/hardware")
    print("Press Ctrl+C to stop server.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down litrun server...")
        server.server_close()
