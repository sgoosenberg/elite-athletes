"""Build only the empty public application form; never read applicant data."""
from pathlib import Path
from portal import render_page


def build():
    page = render_page([])
    page = page.replace('<button type="submit">', '<button type="submit" disabled>')
    page = page.replace('<h2>Join the community</h2>', '<h2>Join the community</h2><p id="notice" role="status" aria-live="polite"></p><noscript>Enable JavaScript to submit an application.</noscript>')
    page = page.replace('</head>', '<style>.portal {display:block; max-width:720px; margin:auto}</style><script src="./config.js" defer></script><script src="./app.js" defer></script></head>')
    Path('docs/index.html').write_text(page)


if __name__ == '__main__':
    build()
