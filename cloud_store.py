"""Server-only Supabase persistence for the free hosted deployment."""
import json
import os
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


class StorageError(OSError):
    pass


def configuration():
    url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    key = os.environ.get('SUPABASE_SECRET_KEY', '')
    if urlsplit(url).scheme != 'https' or not urlsplit(url).hostname or not key:
        raise StorageError('Configure the Supabase project URL and server secret key.')
    return url, key


def request(path, method='GET', data=None, content_type='application/json', headers=None):
    url, key = configuration()
    request_headers = {'apikey': key, 'Content-Type': content_type}
    # Legacy service_role JWTs also require the Authorization header.
    if not key.startswith('sb_secret_'):
        request_headers['Authorization'] = 'Bearer ' + key
    request_headers.update(headers or {})
    body = json.dumps(data).encode() if data is not None and content_type == 'application/json' else data
    try:
        with urlopen(Request(url + path, data=body, headers=request_headers, method=method), timeout=90) as response:
            payload = response.read()
            return json.loads(payload) if payload else None
    except (OSError, ValueError) as error:
        # Do not expose provider responses or credentials to applicants.
        raise StorageError('Cloud storage is unavailable. Please try again shortly.') from error


def load_names():
    entries, offset = [], 0
    while True:
        page = request(f'/rest/v1/athlete_submissions?select=*&order=created_at.asc,id.asc&limit=500&offset={offset}')
        if not isinstance(page, list):
            raise StorageError('Unexpected cloud storage response.')
        entries.extend(page)
        if len(page) < 500:
            return entries
        offset += len(page)


def save_entry(entry):
    fields = ('id', 'name', 'phone', 'history', 'status', 'highlights_url', 'highlights_video')
    record = {field: entry.get(field, '') for field in fields}
    request('/rest/v1/athlete_submissions?on_conflict=id', 'POST', [record],
            headers={'Prefer': 'resolution=merge-duplicates,return=minimal'})


def save_video(filename, payload, mime):
    request('/storage/v1/object/highlights/' + quote(filename, safe=''), 'POST', payload, mime)


def signed_video_url(filename):
    result = request('/storage/v1/object/sign/highlights/' + quote(filename, safe=''), 'POST', {'expiresIn': 300})
    signed = result.get('signedURL', '') if isinstance(result, dict) else ''
    if not signed.startswith('/object/sign/'):
        raise StorageError('Could not open this video.')
    return configuration()[0] + '/storage/v1' + signed
