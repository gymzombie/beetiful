from flask import Flask, jsonify, request, render_template
import os
import subprocess
import logging
import functools

import yaml

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
)
logger = logging.getLogger('beetiful')


def env_flag(name, default=False):
    """Parse a boolean environment variable.

    Returns True only for explicit truthy values ('1', 'true', 'yes', 'on');
    anything else — including an unset variable — returns `default`.
    """
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


app = Flask(__name__)

beets_config_dir = os.getenv('BEETSDIR', os.path.expanduser('~/.config/beets'))

# beets' default config filename is config.yaml, but tolerate config.yml too.
# The first name is the canonical location used when creating a new file.
CONFIG_FILENAMES = ('config.yaml', 'config.yml')


def resolve_config_path(must_exist=False):
    """Return the beets config file path.

    Prefers an existing config.yaml, then config.yml. If neither exists and
    must_exist is False, returns the canonical config.yaml path (where a new
    file should be created). If must_exist is True and none exist, returns None.
    """
    for name in CONFIG_FILENAMES:
        candidate = os.path.join(beets_config_dir, name)
        if os.path.isfile(candidate):
            return candidate
    return None if must_exist else os.path.join(beets_config_dir, CONFIG_FILENAMES[0])


# Where to point users who have no library yet.
BEETS_DOCS_URL = 'https://beets.readthedocs.io/en/stable/guides/main.html'


def resolve_library_path():
    """Return the beets library database path, mirroring beets' own resolution.

    Uses the `library:` setting from the config if present (expanding `~`/env
    vars and resolving relative paths against BEETSDIR), otherwise falls back to
    beets' default of `library.db` inside BEETSDIR. Does not touch beets, so it
    never creates the database as a side effect.
    """
    config_path = resolve_config_path(must_exist=True)
    library = None
    if config_path is not None:
        try:
            with open(config_path, 'r') as file:
                config = yaml.safe_load(file) or {}
            if isinstance(config, dict):
                library = config.get('library')
        except (OSError, yaml.YAMLError) as e:
            logger.warning('Could not read library path from %s: %s', config_path, e)

    if not library:
        return os.path.join(beets_config_dir, 'library.db')

    library = os.path.expanduser(os.path.expandvars(str(library)))
    if not os.path.isabs(library):
        library = os.path.join(beets_config_dir, library)
    return library


def library_missing_response():
    """If no beets library exists, return a Flask response; otherwise None.

    Callers invoke this before shelling out to beets so the app never triggers
    beets into creating a fresh (empty) library just from a page load.
    """
    library_path = resolve_library_path()
    if os.path.isfile(library_path):
        return None
    logger.warning('No beets library found at %s; not invoking beets', library_path)
    return jsonify({
        'no_library': True,
        'library_path': library_path,
        'message': (
            f"No music library found at {library_path}. Beetiful will not "
            f"create one for you. Create a beets library the app can access, "
            f"then reload."
        ),
        'docs_url': BEETS_DOCS_URL,
    }), 409


def requires_library(view):
    """Block a beets-invoking view when no library exists.

    Enforces the rule that the app never creates a library as a side effect:
    if the database is missing, respond with the 'no_library' payload instead
    of shelling out to beets (which would create an empty one).
    """
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        guard = library_missing_response()
        if guard is not None:
            return guard
        return view(*args, **kwargs)
    return wrapped


logger.info('Beets config directory (BEETSDIR): %s', beets_config_dir)
logger.info('Looking for beets config (%s) in: %s', ' or '.join(CONFIG_FILENAMES), beets_config_dir)


def check_config_file():
    """Report the beets config file's status at startup.

    Non-fatal: the file may be created later (e.g. via the config editor or a
    mounted volume that appears after boot), so a missing file is a warning,
    not an exit. This surfaces the problem in the logs immediately rather than
    only when the webapp first requests /api/config.
    """
    config_path = resolve_config_path(must_exist=True)
    if config_path is None:
        expected = os.path.join(beets_config_dir, CONFIG_FILENAMES[0])
        logger.warning(
            'Beets config file not found in %s (BEETSDIR=%s); config editing '
            'and beets commands may fail until %s exists',
            beets_config_dir, beets_config_dir, expected,
        )
    elif not os.access(config_path, os.R_OK):
        logger.warning(
            'Beets config file at %s exists but is not readable (check permissions)',
            config_path,
        )
    else:
        logger.info('Beets config file found at %s', config_path)


check_config_file()


@app.route('/api/config', methods=['GET'])
def view_config():
    """Fetch the configuration as raw text."""
    config_path = resolve_config_path(must_exist=True)
    if config_path is None:
        expected = os.path.join(beets_config_dir, CONFIG_FILENAMES[0])
        logger.error('Config file not found in %s (BEETSDIR=%s)', beets_config_dir, beets_config_dir)
        return f"Config file not found at {expected}.", 404
    logger.info('Loading beets config from %s', config_path)
    try:
        with open(config_path, 'r') as file:
            config_text = file.read()
        logger.info('Loaded beets config from %s', config_path)
        return config_text, 200
    except PermissionError:
        logger.error('Permission denied reading config file at %s', config_path)
        return f"Permission denied reading config file at {config_path}.", 403
    except Exception:
        logger.exception('Error loading config from %s', config_path)
        return f"Error loading config from {config_path}.", 500

@app.route('/api/config', methods=['POST'])
def edit_config():
    """Save the configuration as raw text after validating it is YAML."""
    try:
        config_text = request.data.decode('utf-8')
    except UnicodeDecodeError:
        logger.error('Rejected config save: request body is not valid UTF-8')
        return jsonify({'error': 'Configuration must be valid UTF-8 text.'}), 400

    # Refuse to write content that is not a valid YAML mapping. A beets config
    # is always a mapping of settings; requiring that stops a stray payload
    # (e.g. the "Config file not found..." error text echoed back from the
    # editor, which is a valid YAML *string*) from clobbering the file on disk.
    try:
        parsed = yaml.safe_load(config_text)
    except yaml.YAMLError as e:
        logger.error('Rejected config save: content is not valid YAML: %s', e)
        return jsonify({'error': f"Configuration is not valid YAML: {str(e)}"}), 400

    if parsed is not None and not isinstance(parsed, dict):
        logger.error(
            'Rejected config save: parsed YAML is %s, expected a mapping',
            type(parsed).__name__,
        )
        return jsonify({'error': 'Configuration must be a YAML mapping (key: value settings).'}), 400

    config_path = resolve_config_path()
    try:
        with open(config_path, 'w') as file:
            file.write(config_text)
        logger.info('Saved beets config to %s', config_path)
        return jsonify({'message': 'Configuration updated successfully'}), 200
    except Exception as e:
        logger.exception('Failed to save configuration to %s', config_path)
        return jsonify({'error': f"Failed to save configuration: {str(e)}"}), 500

@app.route('/')
def home():
    return render_template('index.html')


def run_beet(args, **kwargs):
    """Run a `beet` command, logging the invocation.

    The app shells out to beets for stats, listing, and edits; routing every
    call through here makes each invocation visible in the logs.
    """
    logger.info('Invoking beets: %s', ' '.join(args))
    kwargs.setdefault('capture_output', True)
    kwargs.setdefault('text', True)
    return subprocess.run(args, **kwargs)


# Ordered library fields fetched from beets. `id` is first and is beets' stable
# track identifier: it is carried through to the frontend so edits and removals
# target an exact track (id:<n>) instead of an ambiguous title/artist/album
# match. Both the `beet list` format string and the parser derive from this one
# list, so they can never drift out of sync.
LIBRARY_FIELDS = ('id', 'title', 'artist', 'album', 'genre',
                  'year', 'bpm', 'composer', 'comments')

# Field delimiter for `beet list -f`. ASCII Unit Separator (0x1f) never appears
# in tag text, so splitting on it is robust where the old '@@' could collide
# with a value (e.g. a title containing '@@'). Residual known limitation,
# unchanged from before: a literal newline inside a field would still break the
# per-line record splitting.
LIST_SEP = '\x1f'
LIBRARY_FORMAT = LIST_SEP.join(f'${field}' for field in LIBRARY_FIELDS)


def track_selector(data):
    """Return beets query args identifying a single track, or None.

    Prefers the stable `id` when the client supplies it; otherwise falls back to
    the title/artist/album triple (accepting the `original*` keys the edit form
    sends) for backward compatibility. Returns None when neither is usable — the
    caller must reject that rather than run an empty beets query, which would
    match (and modify/remove) the entire library.
    """
    track_id = data.get('id')
    if track_id not in (None, ''):
        return [f'id:{track_id}']

    title = data.get('title') or data.get('originalTitle')
    artist = data.get('artist') or data.get('originalArtist')
    album = data.get('album') or data.get('originalAlbum')
    if not (title and artist and album):
        return None
    return [f'title:{title}', f'artist:{artist}', f'album:{album}']


@app.route('/api/stats', methods=['GET'])
@requires_library
def get_stats():
    """Fetch statistics from beets."""
    result = run_beet(['beet', 'stats'])
    if result.returncode == 0:
        stats = parse_stats(result.stdout)
        return jsonify(stats)
    else:
        return jsonify({'error': result.stderr}), 500


@app.route('/api/run-command', methods=['POST'])
@requires_library
def run_command():
    """Run a command using beets."""
    command = request.json.get('command')
    options = request.json.get('options', [])
    arguments = request.json.get('arguments', [])

    full_command = ['beet', command] + options + arguments

    try:
        result = run_beet(full_command)
        if result.returncode == 0:
            return jsonify({'output': result.stdout.splitlines()})
        else:
            return jsonify({'error': result.stderr}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/library', methods=['GET'])
@requires_library
def get_library():
    """Fetch the library items, including a stable id for each track."""
    result = run_beet(['beet', 'list', '-f', LIBRARY_FORMAT])
    if result.returncode == 0:
        items = [parse_library_item(line) for line in result.stdout.splitlines()]
        return jsonify({'items': items})
    else:
        return jsonify({'error': result.stderr}), 500

def parse_library_item(line):
    """Parse one `beet list` line into a dict keyed by LIBRARY_FIELDS.

    Splitting on LIST_SEP (not '@@') keeps values that contain '@@' intact.
    Missing trailing fields default to '' so a short line never raises.
    """
    values = line.split(LIST_SEP)
    return {
        field: (values[i] if i < len(values) else '')
        for i, field in enumerate(LIBRARY_FIELDS)
    }


        
@app.route('/api/library/remove', methods=['POST'])
@requires_library
def remove_track():
    data = request.json
    selector = track_selector(data)
    if selector is None:
        return jsonify({'error': 'Missing track identifier (id or title/artist/album).'}), 400

    remove_command = ['beet', 'remove', '-f'] + selector
    try:
        run_beet(remove_command, check=True)
        return jsonify({'message': 'Track removed from library.'})
    except subprocess.CalledProcessError as e:
        logger.error('Error removing track: %s', e.stderr)
        return jsonify({'error': e.stderr}), 500


@app.route('/api/library/delete', methods=['POST'])
@requires_library
def delete_track():
    data = request.json
    selector = track_selector(data)
    if selector is None:
        return jsonify({'error': 'Missing track identifier (id or title/artist/album).'}), 400

    command = ['beet', 'remove', '-f'] + selector
    try:
        run_beet(command, check=True)
        return jsonify({'message': 'Track removed from library.'})
    except subprocess.CalledProcessError as e:
        logger.error('Error deleting track: %s', e.stderr)
        return jsonify({'error': e.stderr}), 500


@app.route('/api/library/update', methods=['POST'])
@requires_library
def update_track():
    data = request.json
    updated_track = data.get('updatedTrack', {})

    selector = track_selector(data)
    if selector is None:
        return jsonify({'error': 'Missing track identifier (id or title/artist/album).'}), 400

    command = ['beet', 'modify', '-y'] + selector
    for field, value in updated_track.items():
        if value:
            command.append(f'{field}={value}')

    result = run_beet(command)
    if result.returncode != 0:
        logger.error('Error updating track: %s', result.stderr)
        return jsonify({'error': result.stderr}), 500

    return jsonify({'message': 'Track updated successfully.'})


def parse_stats(output):
    """Parse the stats output from beets."""
    lines = output.splitlines()
    stats = {}
    for line in lines:
        if 'Tracks:' in line:
            stats['total_tracks'] = line.split(': ')[1]
        elif 'Albums:' in line:
            stats['total_albums'] = line.split(': ')[1]
        elif 'Artists:' in line:
            stats['total_artists'] = line.split(': ')[1]
        elif 'Total size:' in line:
            stats['total_size'] = line.split(': ')[1].split(' ')[0]  
    return stats

# Read port from environment variable, defaulting to 3000 if not set
port = int(os.getenv("FLASK_PORT", 3000))

if __name__ == '__main__':
    # Debug is OFF unless FLASK_DEBUG is explicitly enabled: the Werkzeug
    # debugger exposes an interactive console (RCE) on any unhandled exception.
    app.run(debug=env_flag('FLASK_DEBUG'), host='0.0.0.0', port=port)

