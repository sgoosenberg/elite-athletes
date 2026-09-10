from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html import escape
from email.parser import BytesParser
from email.policy import default
import re
import base64
import hmac
import secrets
import cloud_store
from pathlib import Path
import json
import csv
import os
import tempfile
from threading import RLock
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4


HOST = "127.0.0.1"  # Never bind the admin server to a network interface.
PORT = int(os.environ.get("PORT", "8000"))
PUBLIC_ORIGIN = os.environ.get("ELITE_ATHLETES_PUBLIC_ORIGIN", "")
VIDEO_UPLOADS = os.environ.get("ELITE_ATHLETES_VIDEO_UPLOADS", "1") == "1"
PUBLIC_ONLY = os.environ.get("ELITE_ATHLETES_PUBLIC_ONLY") == "1"
PORTAL_PATH = "/elite-athletes"
BACKEND_PATH = "/elite-athletes-backend"
CLOUD_STORAGE = os.environ.get("ELITE_ATHLETES_STORAGE") == "supabase"
HOSTED = os.environ.get("ELITE_ATHLETES_HOSTED") == "1"
ADMIN_PASSWORD = os.environ.get("ELITE_ATHLETES_ADMIN_PASSWORD", "")
CSRF_TOKEN = secrets.token_urlsafe(32)
STORAGE_DIR = Path(os.environ.get("ELITE_ATHLETES_DATA_DIR", str(Path(__file__).parent)))
DATA_FILE = STORAGE_DIR / "names.json"
EXPORT_DIR = STORAGE_DIR / "exports" if HOSTED else Path.home() / "Desktop" / "elite athletes"
DATA_LOCK = RLock()
UPLOAD_DIR = STORAGE_DIR / "uploads"
MAX_VIDEO_BYTES = 50 * 1024 * 1024
VIDEO_TYPES = {".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm"}


def parse_submission(body, content_type):
    if not content_type.lower().startswith("multipart/form-data"):
        return parse_qs(body.decode("utf-8")), None
    message = BytesParser(policy=default).parsebytes(
        ("Content-Type: " + content_type + "\r\nMIME-Version: 1.0\r\n\r\n").encode() + body
    )
    if not message.is_multipart() or message.defects:
        raise ValueError("Invalid upload form.")
    form, video = {}, None
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        payload = part.get_payload(decode=True) or b""
        filename = part.get_filename()
        if filename is not None:
            if not filename:
                continue
            extension = Path(filename).suffix.lower()
            if name != "highlights_video" or extension not in VIDEO_TYPES or video is not None:
                raise ValueError("Choose one MP4, MOV, or WebM video.")
            if not payload or len(payload) > MAX_VIDEO_BYTES:
                raise ValueError("Videos must be nonempty and no larger than 50 MB.")
            valid = (payload[4:8] == b"ftyp" if extension in (".mp4", ".mov")
                     else payload[:4] == b"\x1a\x45\xdf\xa3")
            if not valid:
                raise ValueError("The file does not appear to be a supported video. Try an MP4, MOV, or WebM file.")
            video = (extension, payload)
        else:
            if len(payload) > 10000:
                raise ValueError("A text field is too long.")
            form[name] = [payload.decode("utf-8")]
    return form, video


def valid_highlights_url(url):
    try:
        return len(url) <= 2000 and urlsplit(url).scheme in ("http", "https") and bool(urlsplit(url).hostname)
    except ValueError:
        return False


def render_highlights(entry):
    content = ""
    url = entry.get("highlights_url", "")
    if url and valid_highlights_url(url):
        content += f'<p><a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">Highlights ↗</a></p>'
    video = entry.get("highlights_video", "")
    if re.fullmatch(r"[0-9a-f]{32}\.(mp4|mov|webm)", video):
        content += f'<p>Highlights video</p><video controls preload="metadata" src="/highlights/{video}"></video><p><a href="/highlights/{video}" download>Download video</a></p>'
    return content



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
    writer.writerow(["Name", "Phone number", "Athlete history", "Status", "Highlights link", "Highlights video"])
    writer.writerows(
        (entry.get("name", ""), entry.get("phone", ""), entry.get("history", ""), entry.get("status", "approved"), entry.get("highlights_url", ""), entry.get("highlights_video", ""))
        for entry in names
    )


def load_names():
    if CLOUD_STORAGE:
        return cloud_store.load_names()
    if not DATA_FILE.exists():
        return []

    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            names = json.load(file)
        if not isinstance(names, list):
            return []
        return [
            dict({"id": f"legacy-{index}", "status": "approved", "phone": "", "history": ""},
                 **(entry if isinstance(entry, dict) else {"name": entry}))
            for index, entry in enumerate(names)
        ]
    except (OSError, json.JSONDecodeError):
        return []


def save_names(names):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=DATA_FILE.parent, delete=False) as file:
            temporary = Path(file.name)
            json.dump(names, file, indent=2)
        os.replace(temporary, DATA_FILE)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    export_names(names)


CHICAGO_STYLES = """
:root { color-scheme: light; --ink: #16354a; --muted: #486477; --blue: #83d2f0; --red: #c9253a; --line: #16354a; --font: 'Century Schoolbook', 'New Century Schoolbook', serif; }
* { box-sizing: border-box; }
video { display: block; width: 100%; max-width: 560px; max-height: 360px; border-radius: 12px; background: #16354a; }
.highlights { margin-top: 24px; }
.highlights summary { color: #a51d30; cursor: pointer; text-decoration: underline; font-weight: bold; }
.highlights p { color: var(--muted); font-size: 14px; }
body { margin: 0; min-height: 100vh; color: var(--ink); background: radial-gradient(circle, #83d2f055 1.5px, transparent 1.5px) 0 0 / 22px 22px, #f4fbff; font-family: var(--font); }
body::before { content: ''; display: block; height: 16px; background: var(--blue); border-bottom: 3px solid var(--ink); }
main { width: min(1060px, calc(100% - 40px)); margin: auto; padding: 40px 0 64px; }
.flag { display: flex; gap: 15px; width: fit-content; padding: 10px 22px; margin-bottom: 24px; background: white; border-top: 9px solid var(--blue); border-bottom: 9px solid var(--blue); transform: rotate(-3deg); }
.flag i { display: block; width: 22px; height: 26px; background: var(--red); clip-path: polygon(50% 0%, 63% 28%, 93% 25%, 77% 50%, 93% 75%, 63% 72%, 50% 100%, 37% 72%, 7% 75%, 23% 50%, 7% 25%, 37% 28%); }
.eyebrow { color: var(--red); font-size: 12px; font-weight: 900; text-transform: uppercase; letter-spacing: 2px; margin: 0 0 12px; }
h1, h2, h3 { font-family: var(--font); font-weight: 900; }
h1 { margin: 0; font-size: clamp(48px, 8vw, 92px); line-height: 1.02; letter-spacing: -3px; color: var(--red); }
h2 { margin: 0 0 22px; font-size: 28px; letter-spacing: -1px; }
h3 { margin: 0; font-size: 23px; overflow-wrap: anywhere; }
p { line-height: 1.6; }
.intro { max-width: 630px; margin: 24px 0 32px; font-size: 17px; color: var(--muted); }
.portal { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr); gap: 24px; align-items: start; }
.panel, .review-section { background: white; border: 2px solid var(--ink); border-radius: 22px; padding: 30px; box-shadow: 6px 6px 0 var(--ink); min-width: 0; }
label { display: block; margin: 20px 0 8px; font-size: 12px; font-weight: 900; text-transform: uppercase; letter-spacing: 1px; }
input:not([type=hidden]), textarea { display: block; width: 100%; border: 2px solid var(--ink); border-radius: 12px; padding: 14px; color: var(--ink); background: white; font: 16px/1.5 var(--font); }
input::placeholder, textarea::placeholder { color: #5b6c78; opacity: 1; }
textarea { min-height: 90px; height: 90px; resize: vertical; }
:focus-visible { outline: 3px solid #005b8a; outline-offset: 4px; }
button { border: 2px solid var(--ink); border-radius: 12px; padding: 14px 24px; color: white; background: var(--red); font: 900 17px var(--font); cursor: pointer; box-shadow: 3px 3px 0 var(--ink); transition: transform .12s, box-shadow .12s; }
button:hover { transform: translate(-1px, -2px); box-shadow: 4px 5px 0 var(--ink); }
button:active { transform: translate(2px, 2px); box-shadow: none; }
.panel button { width: 100%; margin-top: 24px; }
.list-heading { display: flex; align-items: baseline; justify-content: space-between; flex-wrap: wrap; gap: 10px; }
.count, h2 span { display: inline-block; white-space: nowrap; background: var(--blue); border: 1px solid var(--ink); border-radius: 30px; padding: 6px 11px; font: 900 12px var(--font); }
.name-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
.name-list li { padding: 16px; background: #edf8ff; border-radius: 12px; border-left: 5px solid var(--red); font: 900 21px var(--font); overflow-wrap: anywhere; }
.empty { color: var(--muted); padding: 18px; border: 2px dashed #94b4c5; border-radius: 12px; font-size: 15px; }
.notice { padding: 14px; border: 2px solid var(--ink); border-radius: 12px; font-size: 14px; margin: 0 0 20px; }
.success { color: var(--ink); background: white; }
.error { color: #991c2c; background: #fff0f2; }
a { color: #a51d30; font-weight: bold; text-underline-offset: 4px; }
.back-link { display: inline-block; margin-bottom: 25px; }
.backend h1 { font-size: clamp(42px, 7vw, 76px); }
.review-section { margin-top: 28px; border-top: 10px solid var(--blue); }
.review-section.status-approved { border-top-color: #2688b0; }
.review-section.status-denied { border-top-color: var(--red); }
article { border-top: 2px dashed #b8d9e8; padding: 24px 0; }
article:last-child { padding-bottom: 0; }
.history { white-space: pre-wrap; overflow-wrap: anywhere; color: var(--muted); }
article form { display: flex; flex-wrap: wrap; gap: 12px; }
button.approved { background: var(--blue); color: var(--ink); }
button.denied { background: var(--red); }
@media (max-width: 680px) { main { width: calc(100% - 32px); padding-top: 28px; } .portal { grid-template-columns: 1fr; } .panel, .review-section { padding: 22px; box-shadow: 4px 4px 0 var(--ink); } h1 { letter-spacing: -2px; } }
@media (prefers-reduced-motion: reduce) { button { transition: none; } }
"""

FLAG_MARK = '<div class="flag" aria-hidden="true"><i></i><i></i><i></i><i></i></div>'


def render_page(names, message="", error=False):
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
  <style>{CHICAGO_STYLES}</style>
</head>
<body>
  <main>
    {FLAG_MARK}
    <p class="eyebrow">Elite Athletes applications</p>
    <h1>Elite Athletes</h1>
    <p class="intro">Elite Athletes is a Chicago community for high level pickup sports. Send this to the best athlete you know</p>
    <section class="portal">
      <form class="panel" enctype="multipart/form-data" method="post" action="{PORTAL_PATH}">
        <h2>Join the community</h2>
        {notice}
        <label for="name">Full name</label>
        <input id="name" name="name" type="text" maxlength="80" autocomplete="name" placeholder="e.g. Maya Chen" required autofocus>
        <label for="phone">Phone number</label>
        <input id="phone" name="phone" type="tel" maxlength="30" autocomplete="tel" placeholder="e.g. (555) 123-4567" required>
        <label class="history-label" for="history">Athlete history (optional)</label>
        <textarea id="history" name="history" maxlength="2000" placeholder="Ex: Three sport varsity athlete, football at University of Virginia"></textarea>
        <details class="highlights">
          <summary>Highlights (Optional)</summary>
          <p>Paste a link that shows off your athleticism.</p>
          <label for="highlights-url">Highlights link</label>
          <input id="highlights-url" name="highlights_url" type="url" maxlength="2000" placeholder="https://...">

        </details>
        <button type="submit">Submit</button>
      </form>
    </section>
  </main>
</body>
</html>"""


def render_backend(names):
    sections = []
    for status, title in [("pending", "Pending submissions"), ("approved", "Roster"), ("denied", "Denied submissions")]:
        entries = [entry for entry in reversed(names) if entry.get("status", "approved") == status]
        cards = []
        for entry in entries:
            actions = "".join(
                f'<button name="decision" value="{decision}" class="{decision}">{label}</button>'
                for decision, label in [("approved", "Approve"), ("denied", "Deny")]
                if decision != status
            )
            cards.append(f'''<article>
                <h3>{escape(entry["name"])}</h3>
                <p>{escape(entry.get("phone", ""))}</p>
                <p class="history">{escape(entry.get("history", "")) or "No athlete history provided."}</p>
                {render_highlights(entry)}
                <form method="post" action="{BACKEND_PATH}">
                    <input type="hidden" name="csrf" value="{CSRF_TOKEN}">
                    <input type="hidden" name="id" value="{escape(entry["id"], quote=True)}">
                    {actions}
                </form>
            </article>''')
        sections.append(f'<section class="review-section status-{status}"><h2>{title} <span>{len(entries)}</span></h2>'
                        + ("".join(cards) or '<p class="empty">No submissions in this section.</p>') + '</section>')
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Elite Athletes Backend</title>
<style>{CHICAGO_STYLES}</style></head><body><main class="backend">
{FLAG_MARK}
<a class="back-link" href="{PORTAL_PATH}">← View Elite Athletes</a>
<h1>Elite Athletes Backend</h1>
<p>Review athlete details and approve or deny submissions. Application details and decisions stay private.</p>
{"".join(sections)}
</main></body></html>'''


class PortalHandler(BaseHTTPRequestHandler):
    def public_headers(self):
        if urlsplit(self.path).path == PORTAL_PATH:
            self.send_header("Vary", "Origin, Accept")
            self.send_header("Cache-Control", "no-store")
            if PUBLIC_ORIGIN and self.headers.get("Origin") == PUBLIC_ORIGIN:
                self.send_header("Access-Control-Allow-Origin", PUBLIC_ORIGIN)

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.public_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def redirect(self, path):
        self.send_response(303)
        self.send_header("Location", path)
        self.end_headers()

    def allow_request(self, path):
        if path in ("/", PORTAL_PATH):
            return True
        if PUBLIC_ONLY:
            self.send_error(403, "Private page")
            return False
        if HOSTED or self.client_address[0] not in ("127.0.0.1", "::1"):
            self.send_error(403, "The admin dashboard is local only.")
            return False
        if self.headers.get("Host", f"127.0.0.1:{PORT}") not in (f"127.0.0.1:{PORT}", f"localhost:{PORT}"):
            self.send_error(403)
            return False
        return True

    def do_GET(self):
        path = urlsplit(self.path).path
        if not self.allow_request(path):
            return
        if path.startswith("/highlights/"):
            filename = path[len("/highlights/"): ]
            if not re.fullmatch(r"[0-9a-f]{32}\.(mp4|mov|webm)", filename):
                self.send_error(404)
                return
            if CLOUD_STORAGE:
                try:
                    self.redirect(cloud_store.signed_video_url(filename))
                except OSError:
                    self.send_error(503, "Video storage is unavailable.")
                return
            try:
                video = (UPLOAD_DIR / filename).read_bytes()
            except OSError:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", VIDEO_TYPES[Path(filename).suffix])
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(video)))
            self.end_headers()
            self.wfile.write(video)
            return
        if path == "/":
            self.redirect(PORTAL_PATH)
            return
        if path not in (PORTAL_PATH, BACKEND_PATH):
            self.send_error(404)
            return
        with DATA_LOCK:
            names = load_names()
            if path == PORTAL_PATH and self.headers.get("Accept") == "application/json":
                self.send_error(404)
                return
            if path == BACKEND_PATH:
                content = render_backend(names)
            else:
                submitted = parse_qs(urlsplit(self.path).query).get("submitted") == ["1"]
                content = render_page(names, "Application received! The organizer will review your submission." if submitted else "")
        self.send_html(content)

    def do_POST(self):
        path = urlsplit(self.path).path
        if not self.allow_request(path):
            return
        if path not in (PORTAL_PATH, BACKEND_PATH):
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= (MAX_VIDEO_BYTES + 20000 if VIDEO_UPLOADS else 20000):
                raise ValueError("Submission too large.")
            form, video = parse_submission(self.rfile.read(length), self.headers.get("Content-Type", "application/x-www-form-urlencoded"))
            if video and not VIDEO_UPLOADS:
                raise ValueError("Video uploads are disabled. Please use a highlights link.")
        except (ValueError, UnicodeDecodeError) as exc:
            self.send_html(render_page(load_names(), str(exc), error=True), 400)
            return
        with DATA_LOCK:
            names = load_names()
            if path == BACKEND_PATH:
                if not hmac.compare_digest(form.get("csrf", [""])[0], CSRF_TOKEN):
                    self.send_error(403, "Reload the backend before submitting a decision.")
                    return
                decision = form.get("decision", [""])[0]
                entry_id = form.get("id", [""])[0]
                if decision not in ("approved", "denied"):
                    self.send_error(400, "Invalid decision")
                    return
                entry = next((entry for entry in names if entry["id"] == entry_id), None)
                if entry is None:
                    self.send_error(404, "Submission not found")
                    return
                entry["status"] = decision
            else:
                name = form.get("name", [""])[0].strip()
                phone = form.get("phone", [""])[0].strip()
                history = form.get("history", [""])[0].strip()
                if not name or not phone or len(name) > 80 or len(phone) > 30 or len(history) > 2000:
                    self.send_html(render_page(names, "Enter a name (up to 80 characters), phone number (up to 30), and optional history (up to 2,000).", error=True), 400)
                    return
                highlights_url = form.get("highlights_url", [""])[0].strip()
                if highlights_url and not valid_highlights_url(highlights_url):
                    self.send_html(render_page(names, "Enter a valid highlights link starting with https:// or http://.", error=True), 400)
                    return
                entry = {"id": uuid4().hex, "name": name, "phone": phone, "history": history, "status": "pending", "highlights_url": highlights_url}
                if video:
                    extension, payload = video
                    filename = uuid4().hex + extension
                    try:
                        if CLOUD_STORAGE:
                            cloud_store.save_video(filename, payload, VIDEO_TYPES[extension])
                        else:
                            UPLOAD_DIR.mkdir(exist_ok=True)
                            (UPLOAD_DIR / filename).write_bytes(payload)
                    except OSError:
                        self.send_html(render_page(names, "Could not save the video. Storage may be full or unavailable. Try a highlights link instead.", error=True), 500)
                        return
                    entry["highlights_video"] = filename
                names.append(entry)
            try:
                if CLOUD_STORAGE:
                    cloud_store.save_entry(entry)
                else:
                    save_names(names)
            except OSError:
                self.send_html("<p>Could not finish saving your submission or decision. Reload to check whether it saved before trying again.</p>", 500)
                return
        if path == PORTAL_PATH and self.headers.get("Accept") == "application/json":
            self.send_json({"submitted": True}, 201)
            return
        self.redirect(BACKEND_PATH if path == BACKEND_PATH else PORTAL_PATH + "?submitted=1")

    def send_html(self, content, status=200):
        body = content.encode("utf-8")
        self.send_response(status)
        self.public_headers()
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def main():
    if HOSTED or os.environ.get("ELITE_ATHLETES_HOST", "127.0.0.1") != "127.0.0.1":
        raise SystemExit("Admin is local only. Hosted and network binding modes are disabled.")
    server = ThreadingHTTPServer((HOST, PORT), PortalHandler)
    print(f"Local admin: http://127.0.0.1:{PORT}{BACKEND_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
