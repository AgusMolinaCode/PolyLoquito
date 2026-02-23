"""
Health Check Server para Railway
================================
Expone un endpoint HTTP para que Railway pueda verificar
que el bot está funcionando correctamente.

Uso:
  python health_server.py  # Inicia servidor en puerto 8080
"""

import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from main import health_check

PORT = int(os.environ.get("PORT", 8080))


class HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Silenciar logs del servidor HTTP
        pass
    
    def do_GET(self):
        if self.path == "/health":
            health = health_check()
            status_code = 200 if health["status"] == "running" else 503
            
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(health).encode())
        else:
            self.send_response(404)
            self.end_headers()


def run_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    print(f"Health server escuchando en puerto {PORT}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
