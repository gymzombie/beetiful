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
    """Fetch the library items including genre information."""
    result = run_beet(['beet', 'list', '-f', '$title@@$artist@@$album@@$genre@@$year@@$bpm@@$composer@@$comments'])
    if result.returncode == 0:
        items = [parse_library_item(line) for line in result.stdout.splitlines()]
        return jsonify({'items': items})
    else:
        return jsonify({'error': result.stderr}), 500

def parse_library_item(line):
    """Parse a library item from the list output."""
    fields = line.split('@@')  
    return {
        'title': fields[0] if len(fields) > 0 else '',
        'artist': fields[1] if len(fields) > 1 else '',
        'album': fields[2] if len(fields) > 2 else '',
        'genre': fields[3] if len(fields) > 3 else '',
        'year': fields[4] if len(fields) > 4 else '',
        'bpm': fields[5] if len(fields) > 5 else '',
        'composer': fields[6] if len(fields) > 6 else '',
        'comments': fields[7] if len(fields) > 7 else ''
    }


        
@app.route('/api/library/remove', methods=['POST'])
@requires_library
def remove_track():
    data = request.json
    title = data.get('title')
    artist = data.get('artist')
    album = data.get('album')

    
    id_command = ['beet', 'list', '-f', '$id', f'title:{title}', f'artist:{artist}', f'album:{album}']
    id_result = run_beet(id_command)

    if id_result.returncode != 0 or not id_result.stdout.strip():
        print(f"Error finding track ID: {id_result.stderr}")
        return jsonify({'error': 'Track not found for removal.'}), 500

    track_id = id_result.stdout.strip()
    print(f"Found track ID: {track_id}")

    
    remove_command = ['beet', 'remove', '-f', f'id:{track_id}']
    print(f"Executing remove command: {' '.join(remove_command)}")

    try:
        result = run_beet(remove_command, check=True)
        print("Track removed from library.")
        return jsonify({'message': 'Track removed from library.'})
    except subprocess.CalledProcessError as e:
        print(f"Error removing track: {e.stderr}")
        return jsonify({'error': e.stderr}), 500


@app.route('/api/library/delete', methods=['POST'])
@requires_library
def delete_track():
    data = request.json
    print(f"Delete request received with data: {data}")  
    title = data.get('title')
    artist = data.get('artist')
    album = data.get('album')

    if not title or not artist or not album:
        print("Error: Missing required fields for delete command.")  
        return jsonify({'error': 'Missing required fields'}), 400

    
    command = ['beet', 'remove', '-f', f'title:{title}', f'artist:{artist}', f'album:{album}']
    print(f"Executing delete command: {' '.join(command)}")

    try:
        result = run_beet(command, check=True)
        print("Track deleted successfully.")  
        return jsonify({'message': 'Track removed from library.'})
    except subprocess.CalledProcessError as e:
        print(f"Error deleting track: {e.stderr}")  
        return jsonify({'error': e.stderr}), 500




@app.route('/api/library/update', methods=['POST'])
@requires_library
def update_track():
    data = request.json
    original_title = data.get('originalTitle', '')
    original_artist = data.get('originalArtist', '')
    original_album = data.get('originalAlbum', '')
    updated_track = data.get('updatedTrack', {})

    
    command = ['beet', 'modify', '-y', f'title:{original_title}', f'artist:{original_artist}', f'album:{original_album}']

    
    for field, value in updated_track.items():
        if value:  
            command.append(f'{field}={value}')

    
    print(f"Executing command: {' '.join(command)}")

    
    result = run_beet(command)


    if result.returncode != 0:
        print(f"Error: {result.stderr}")
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
    app.run(debug=True, host='0.0.0.0', port=port)

