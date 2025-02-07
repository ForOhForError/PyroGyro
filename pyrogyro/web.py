import json
import logging
import threading

from flask import Flask
from flask import cli as flask_cli
from flask import render_template, send_file
from flask_sock import Sock

from pyrogyro.constants import DEBUG, ROOT_DIR, icon_location

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5000


class WebServer:
    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        web_dir = ROOT_DIR / "res" / "web"
        self.app = Flask(
            __name__,
            static_url_path="",
            static_folder=web_dir / "static",
            template_folder=web_dir / "templates",
        )
        logging.getLogger("werkzeug").disabled = True
        self.host = host
        self.port = port
        self.logger = logging.getLogger("WebServer")
        self.app.logger.addHandler(logging.getLogger("WebServer"))
        self.sock_app = Sock(self.app)
        self.app.config["SOCK_SERVER_OPTIONS"] = {"ping_interval": 25}
        self.app.add_url_rule("/", "index", self.index)
        self.app.add_url_rule("/favicon.ico", "favicon", self.favicon)
        self.ws_conns = set()
        self.conn_lock = threading.Lock()

        @self.sock_app.route("/ws")
        def _(ws):
            self.handle_ws(ws)

    def handle_ws(self, ws):
        with self.conn_lock:
            self.ws_conns.add(ws)
        try:
            while True:
                self.handle_ws_message(ws, ws.receive())
        except Exception:
            with self.conn_lock:
                self.ws_conns.discard(ws)

    def handle_ws_message(self, ws, message):
        pass

    def send_message(self, message_obj):
        with self.conn_lock:
            for ws in self.ws_conns:
                ws.send(json.dumps(message_obj))

    def index(self):
        return render_template("display.html", host=self.host, port=self.port)

    def favicon(self):
        return send_file(icon_location())

    def get_local_url(self):
        return f"http://{self.host}:{self.port}"

    def open_web_ui(self, *args):
        url = self.get_local_url()
        try:
            import webbrowser

            webbrowser.open(url)
        except Exception:
            self.logger.info(
                f"Tried to open a browser window to view Web UI at {url} but failed."
            )
            pass

    def run_server(self):
        flask_cli.show_server_banner = lambda *x: None
        self.logger.info(f"Starting Web Console Server at {self.get_local_url()}")
        self.app.run(debug=DEBUG, use_reloader=False, host=self.host, port=self.port)

    def run_in_thread(self):
        server_thread = threading.Thread(target=self.run_server, daemon=True)
        server_thread.start()
        return server_thread
