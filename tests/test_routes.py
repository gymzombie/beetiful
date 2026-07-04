"""Route-contract test.

Guards against the class of bug behind issues #4 and #5: front-end code
referencing a server path (`/library.html`, `/api/debug_library`) that has no
matching Flask route, producing silent 404s. Every absolute-path string literal
in the static JS must resolve to a registered route.
"""
import os
import re
import pathlib

import pytest
from werkzeug.exceptions import MethodNotAllowed, NotFound

from beetiful import app

STATIC_JS = pathlib.Path(app.root_path) / 'static' / 'js'

# Quoted absolute-path literals, e.g. '/api/library' or '/library.html'.
PATH_LITERAL = re.compile(r"""['"](/[A-Za-z0-9_./-]*)['"]""")


def _referenced_paths():
    """Yield (js_file, path) for every internal path literal in the JS."""
    for js_file in sorted(STATIC_JS.glob('*.js')):
        text = js_file.read_text()
        for match in PATH_LITERAL.finditer(text):
            path = match.group(1)
            # Static assets are served by Flask's built-in /static/<path> rule
            # but are referenced with concrete filenames, so skip them here.
            if path.startswith('/static/'):
                continue
            yield js_file.name, path


def _route_exists(path):
    """True if `path` matches any registered route (any HTTP method)."""
    adapter = app.url_map.bind('localhost')
    try:
        adapter.match(path, method='GET')
    except MethodNotAllowed:
        return True  # route exists, just not for GET
    except NotFound:
        return False
    return True


REFERENCED = list(_referenced_paths())


@pytest.mark.parametrize('js_file,path', REFERENCED, ids=[f"{f}:{p}" for f, p in REFERENCED])
def test_referenced_path_has_route(js_file, path):
    assert _route_exists(path), (
        f"{js_file} references {path!r}, which has no matching Flask route. "
        f"Either add the route or fix the reference."
    )


def test_found_some_paths():
    """Sanity check that the scanner actually found references to validate."""
    assert REFERENCED, "No path literals discovered — the scanner regex may be broken."
