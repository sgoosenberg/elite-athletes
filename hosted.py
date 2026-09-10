"""Retired deployment entry point. No Python dashboard routes are hosted."""
def application(environ, start_response):
    start_response('410 Gone', [('Content-Type', 'text/plain'), ('Cache-Control', 'no-store')])
    return [b'This service has been retired.']
