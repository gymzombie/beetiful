"""Static guards against reintroducing the stored-XSS patterns from issue #2.

The library table renders attacker-influenceable track metadata (imported tag
values). It must be inserted via textContent / element.value, never built into
HTML or inline event-handler strings. These checks fail if the dangerous
constructs come back.
"""
import re
import pathlib

from beetiful import app

LIBRARY_JS = (pathlib.Path(app.root_path) / 'static' / 'js' / 'library.js').read_text()


def test_no_inline_onclick_handlers():
    """Inline onclick="..." attributes interpolate data into a JS/HTML context;
    use addEventListener instead so metadata is never parsed as code.

    Note: `element.onclick = fn` property assignments (no quote after =) are safe
    and intentionally not matched here.
    """
    offenders = re.findall(r'''onclick\s*=\s*["']''', LIBRARY_JS)
    assert not offenders, f"found {len(offenders)} inline onclick=\"...\" handler(s) in library.js"


def test_no_interpolated_innerhtml():
    """innerHTML must never be assigned a template literal containing ${...};
    that would inject untrusted values. Static/empty strings are fine."""
    offenders = re.findall(r'innerHTML\s*=\s*`[^`]*\$\{', LIBRARY_JS)
    assert not offenders, "innerHTML assigned an interpolated template literal in library.js"


def test_track_object_not_serialized_into_markup():
    """The Edit button must not embed JSON.stringify(item) in markup."""
    assert 'JSON.stringify(item)' not in LIBRARY_JS
