"""Build only the empty public application form; never read applicant data."""
from pathlib import Path
from hashlib import sha256
from portal import render_page


def build():
    page = render_page([])
    page = page.replace('<button type="submit">', '<button type="submit" disabled>')
    page = page.replace('<h2>Join the community</h2>', '<h2>Join the community</h2><p id="notice" role="status" aria-live="polite"></p><noscript>Enable JavaScript to submit an application.</noscript>')
    page = page.replace('</form>', '</form><aside class="panel" aria-labelledby="roster-heading"><h2 id="roster-heading">Roster</h2><p id="roster-status" role="status">Loading roster…</p><ul id="roster-list"></ul></aside>')
    page = page.replace('</head>', '<style>.portal {display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,1fr)} #roster-list {padding-left:1.3rem} #roster-list li {padding:8px 0;overflow-wrap:anywhere} @media(max-width:700px){.portal{grid-template-columns:1fr}}</style><script src="./config.js" defer></script><script src="./app.js" defer></script></head>')
    for script in ('config.js', 'app.js'):
        version = sha256(Path('docs', script).read_bytes()).hexdigest()[:12]
        page = page.replace(f'./{script}"', f'./{script}?v={version}"')
    Path('docs/index.html').write_text(page)


if __name__ == '__main__':
    build()
