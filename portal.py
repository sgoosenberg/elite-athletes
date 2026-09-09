from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html import escape
from pathlib import Path
import json
import csv
import os
import tempfile
from threading import RLock
from urllib.parse import parse_qs


HOST = "127.0.0.1"
PORT = 8000
PORTAL_PATH = "/elite-athletes"
DATA_FILE = Path(__file__).with_name("names.json")
EXPORT_DIR = Path.home() / "Desktop" / "elite athletes"
DATA_LOCK = RLock()


def export_names(names):
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    outputs = {
        "athletes.json": lambda file: json.dump(names, file, indent=2),
        "phone numbers.csv": lambda file: write_contacts_csv(file, names),
    }
    for filename, write in outputs.items():
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="", dir=EXPORT_DIR, delete=False
            ) as file:
                temporary = Path(file.name)
                write(file)
            os.replace(temporary, EXPORT_DIR / filename)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def write_contacts_csv(file, names):
    writer = csv.writer(file)
    writer.writerow(["Name", "Phone number"])
    writer.writerows((entry.get("name", ""), entry.get("phone", "")) for entry in names)


def load_names():
    if not DATA_FILE.exists():
        return []

    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            names = json.load(file)
        if not isinstance(names, list):
            return []
        return [
            entry if isinstance(entry, dict) else {"name": entry, "phone": ""}
            for entry in names
        ]
    except (OSError, json.JSONDecodeError):
        return []


def save_names(names):
    with DATA_FILE.open("w", encoding="utf-8") as file:
        json.dump(names, file, indent=2)
    export_names(names)


def render_page(names, message="", error=False):
    rows = "".join(
    f'<li><div><span>{escape(athlete["name"])}</span><small>{escape(athlete["phone"]) or "No phone added"}</small></div><b>Saved</b></li>'
    for athlete in reversed(names)
    )
    names_content = (
        f'<ul class="name-list">{rows}</ul>'
        if rows
        else '<p class="empty">No names saved yet.</p>'
    )
    notice = (
        f'<p class="notice {"error" if error else "success"}">{escape(message)}</p>'
        if message
        else ""
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Elite Athletes</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #18232d;
      --muted: #64717a;
      --paper: #fffdf8;
      --cream: #f4eee3;
      --coral: #d95d46;
      --coral-dark: #a94334;
      --line: #e5dbcb;
      --green: #3f735b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      background: radial-gradient(circle at 85% 12%, #f5cdb7 0 12%, transparent 28%),
                  linear-gradient(135deg, #f7efe2, #dce8e0 100%);
      font-family: Georgia, "Times New Roman", serif;
    }}
    main {{ width: min(900px, calc(100% - 36px)); margin: 0 auto; padding: 72px 0; }}
    .eyebrow {{ margin: 0 0 16px; color: var(--coral-dark); font: 700 12px/1.2 Arial, sans-serif; letter-spacing: 2px; text-transform: uppercase; }}
    h1 {{ max-width: 600px; margin: 0; font-size: clamp(42px, 8vw, 78px); line-height: .94; font-weight: 400; letter-spacing: -2px; }}
    .intro {{ max-width: 540px; margin: 24px 0 42px; color: var(--muted); font: 17px/1.6 Arial, sans-serif; }}
    .portal {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr); gap: 1px; background: var(--line); border: 1px solid var(--line); box-shadow: 0 20px 50px rgba(61, 54, 42, .12); }}
    .panel {{ padding: 32px; background: var(--paper); }}
    .panel:first-child {{ background: var(--ink); color: white; }}
    h2 {{ margin: 0 0 22px; font-size: 27px; font-weight: 400; }}
    label {{ display: block; margin-bottom: 9px; color: #bac5c6; font: 700 12px/1.2 Arial, sans-serif; letter-spacing: 1.5px; text-transform: uppercase; }}
    input {{ width: 100%; padding: 15px 0; border: 0; border-bottom: 1px solid #718087; outline: 0; color: white; background: transparent; font: 20px Georgia, serif; }}
    input:focus {{ border-color: #ef987d; }}
    button {{ width: 100%; margin-top: 28px; padding: 15px 18px; border: 0; color: white; background: var(--coral); font: 700 14px Arial, sans-serif; cursor: pointer; }}
    button:hover {{ background: #ed765d; }}
    .list-heading {{ display: flex; align-items: baseline; justify-content: space-between; gap: 16px; }}
    .count {{ color: var(--coral-dark); font: 700 12px Arial, sans-serif; }}
    .name-list {{ display: grid; gap: 0; padding: 0; margin: 0; list-style: none; }}
    .name-list li {{ display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 16px 0; border-bottom: 1px solid var(--line); font-size: 20px; }}
    .name-list small {{ display: block; margin-top: 5px; color: var(--muted); font: 14px Arial, sans-serif; }}
    .name-list b {{ color: var(--green); font: 700 10px Arial, sans-serif; letter-spacing: 1px; text-transform: uppercase; }}
    .empty {{ color: var(--muted); font: 15px Arial, sans-serif; }}
    .notice {{ margin: -20px 0 24px; padding: 12px; font: 14px Arial, sans-serif; }}
    .success {{ color: var(--green); background: #e8f2e9; }}
    .error {{ color: #a94334; background: #f9e5df; }}
    @media (max-width: 680px) {{
      main {{ padding: 42px 0; }}
      .portal {{ grid-template-columns: 1fr; }}
      .panel {{ padding: 26px; }}
    }}
  </style>
</head>
<body>
  <main>
    <p class="eyebrow">Elite Athletes directory</p>
    <h1>Elite Athletes</h1>
    <p class="intro">Keep a local directory of your athletes. Names and phone numbers are saved and remain available the next time you open the portal.</p>
    <section class="portal">
      <form class="panel" method="post" action="{PORTAL_PATH}">
        <h2>Add someone</h2>
        {notice}
        <label for="name">Full name</label>
        <input id="name" name="name" type="text" maxlength="80" autocomplete="name" placeholder="e.g. Maya Chen" required autofocus>
        <label for="phone">Phone number</label>
        <input id="phone" name="phone" type="tel" maxlength="30" autocomplete="tel" placeholder="e.g. (555) 123-4567" required>
        <button type="submit">Save athlete</button>
      </form>
      <section class="panel" aria-labelledby="saved-heading">
        <div class="list-heading">
          <h2 id="saved-heading">Saved athletes</h2>
          <span class="count">{len(names)} total</span>
        </div>
        {names_content}
      </section>
    </section>
  </main>
</body>
</html>"""


class PortalHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.send_response(302)
            self.send_header("Location", PORTAL_PATH)
            self.end_headers()
            return

        with DATA_LOCK:
            content = render_page(load_names())
        self.send_html(content)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        form = parse_qs(self.rfile.read(length).decode("utf-8"))
        name = form.get("name", [""])[0].strip()
        phone = form.get("phone", [""])[0].strip()

        if not name or not phone:
            self.send_html(render_page(load_names(), "Please enter both a name and phone number.", error=True), 400)
            return

        with DATA_LOCK:
            names = load_names()
            names.append({"name": name, "phone": phone})
            try:
                save_names(names)
            except OSError:
                self.send_html(render_page(load_names(), "Could not finish saving to the portal and Desktop folder. Check folder permissions and available disk space before trying again.", error=True), 500)
                return
            self.send_html(render_page(names, f"{name} was saved with their phone number."))

    def send_html(self, content, status=200):
        body = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), PortalHandler)
    export_names(load_names())
    print(f"Elite Athletes running at http://{HOST}:{PORT}{PORTAL_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nPortal stopped.")
    finally:
        server.server_close()
