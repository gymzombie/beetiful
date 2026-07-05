// The library table is rendered by Tabulator (loaded via CDN in index.html).
// Tabulator owns sorting, per-column filtering and pagination; this file wires
// it to /api/library, keeps the no-library notice, and drives the edit form.
//
// Security note (issue #2): track metadata is attacker-influenceable (imported
// tag values). Every cell is rendered through textCellFormatter, which sets
// textContent on a DOM node, so values are never parsed as HTML. Buttons are
// wired with addEventListener — never inline onclick or interpolated innerHTML.

let libraryTable = null;

document.addEventListener('DOMContentLoaded', () => {
    initLibraryTable();
    // replaceData must run after the table is built, so load on 'tableBuilt'.
    libraryTable.on('tableBuilt', fetchLibrary);
});

// Render a cell value as plain text — never HTML. Returning a DOM node (rather
// than a string, which Tabulator would treat as HTML) keeps metadata inert.
function textCellFormatter(cell) {
    const span = document.createElement('span');
    span.textContent = cell.getValue() ?? '';
    return span;
}

// The per-row Edit button, wired via addEventListener over the row's data
// (which carries the stable `id`) instead of serializing anything into markup.
function editButtonFormatter(cell) {
    const button = document.createElement('button');
    button.className = 'btn btn-primary btn-sm';
    button.textContent = 'Edit';
    button.addEventListener('click', () => editTrack(cell.getRow().getData()));
    return button;
}

// Shorten a filesystem path to its last two folders + filename
// (e.g. .../Artist/Album/Song.mp3) — the part that matters for most libraries.
// Splits on either separator so it works for POSIX and Windows paths.
function shortPath(fullPath) {
    if (!fullPath) return '';
    const parts = fullPath.split(/[\\/]+/).filter(Boolean);
    const tail = parts.slice(-3);  // two folders + filename
    const short = tail.join('/');
    return parts.length > tail.length ? '…/' + short : short;
}

// Path cell: show the shortened path as text, full path on hover (title
// attribute is inert — never parsed as HTML), preserving the XSS guarantee.
function pathCellFormatter(cell) {
    const fullPath = cell.getValue() ?? '';
    const span = document.createElement('span');
    span.textContent = shortPath(fullPath);
    span.title = fullPath;
    return span;
}

function initLibraryTable() {
    libraryTable = new Tabulator('#libraryTable', {
        height: '75vh',
        layout: 'fitColumns',
        pagination: true,
        paginationMode: 'local',
        paginationSize: 20,
        paginationCounter: 'rows',
        index: 'id',
        placeholder: 'No matching tracks',
        columns: [
            { title: 'Title', field: 'title', headerFilter: 'input', formatter: textCellFormatter },
            { title: 'Artist', field: 'artist', headerFilter: 'input', formatter: textCellFormatter },
            { title: 'Album', field: 'album', headerFilter: 'input', formatter: textCellFormatter },
            { title: 'Genre', field: 'genre', headerFilter: 'input', formatter: textCellFormatter },
            { title: 'Path', field: 'path', headerFilter: 'input', formatter: pathCellFormatter },
            { title: '', headerSort: false, width: 90, formatter: editButtonFormatter },
        ],
    });
    return libraryTable;
}

function fetchLibrary() {
    fetch('/api/library')
        .then(response => response.json())
        .then(data => {
            if (data && data.no_library) {
                showNoLibraryNotice(data);
                return;
            }
            if (Array.isArray(data.items)) {
                hideNoLibraryNotice();
                // replaceData keeps the current sort/header-filter state, so a
                // refresh after an edit doesn't reset the user's view.
                libraryTable.replaceData(data.items);
            } else {
                console.error('Unexpected data format:', data);
            }
        })
        .catch(error => {
            console.error('Error fetching library data:', error);
        });
}

// Clear every column's header filter (the "Clear Filters" button).
function clearFilters() {
    if (libraryTable) libraryTable.clearHeaderFilter();
}

// When no beets library exists, show a focused notice and hide the table,
// stats and filters so the user's only next action is clear.
function showNoLibraryNotice(info) {
    const tableContainer = document.querySelector('.table-container');
    if (tableContainer) tableContainer.style.display = 'none';
    const toolbar = document.getElementById('libraryToolbar');
    if (toolbar) toolbar.style.display = 'none';
    ['totalTracks', 'totalArtists', 'totalAlbums'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = '';
    });

    const docsUrl = (info && info.docs_url) || 'https://beets.readthedocs.io/en/stable/guides/main.html';
    const message = (info && info.message) || 'No music library found.';

    const notice = document.getElementById('libraryNotice');
    notice.innerHTML = '';

    const heading = document.createElement('h5');
    heading.className = 'alert-heading';
    heading.textContent = 'No music library found';

    const messagePara = document.createElement('p');
    messagePara.textContent = message;  // textContent avoids injecting the path

    const helpPara = document.createElement('p');
    helpPara.className = 'mb-0';
    helpPara.appendChild(document.createTextNode('New to beets? See the '));
    const link = document.createElement('a');
    link.href = docsUrl;
    link.target = '_blank';
    link.rel = 'noopener';
    link.textContent = 'beets Getting Started guide';
    helpPara.appendChild(link);
    helpPara.appendChild(document.createTextNode(' to create your library.'));

    notice.append(heading, messagePara, helpPara);
    notice.style.display = 'block';
}

function hideNoLibraryNotice() {
    const notice = document.getElementById('libraryNotice');
    if (notice) notice.style.display = 'none';
    const tableContainer = document.querySelector('.table-container');
    if (tableContainer) tableContainer.style.display = '';
    const toolbar = document.getElementById('libraryToolbar');
    if (toolbar) toolbar.style.display = '';
}

function editTrack(track) {
    const editFormContainer = document.getElementById('editFormContainer');
    editFormContainer.innerHTML = '';
    editFormContainer.style.display = '';

    const heading = document.createElement('h5');
    heading.textContent = 'Edit Track';
    editFormContainer.appendChild(heading);

    // Build each field with DOM APIs; assigning to .value never parses HTML,
    // so metadata containing < > " ' is treated as literal text.
    const textFields = [
        { id: 'editTitle', label: 'Title', value: track.title },
        { id: 'editArtist', label: 'Artist', value: track.artist },
        { id: 'editAlbum', label: 'Album', value: track.album },
        { id: 'editYear', label: 'Year', value: track.year },
        { id: 'editGenre', label: 'Genre', value: track.genre },
        { id: 'editComposer', label: 'Composer', value: track.composer },
        { id: 'editBpm', label: 'BPM', value: track.bpm },
    ];
    textFields.forEach(field => {
        const label = document.createElement('label');
        label.textContent = field.label + ': ';
        const input = document.createElement('input');
        input.type = 'text';
        input.id = field.id;
        input.className = 'form-control';
        input.value = field.value || '';
        label.appendChild(input);
        editFormContainer.appendChild(label);
    });

    const commentsLabel = document.createElement('label');
    commentsLabel.textContent = 'Comments: ';
    const commentsArea = document.createElement('textarea');
    commentsArea.id = 'editComments';
    commentsArea.className = 'form-control';
    commentsArea.value = track.comments || '';
    commentsLabel.appendChild(commentsArea);
    editFormContainer.appendChild(commentsLabel);

    // Read-only full filesystem path: beets manages file location via `move`,
    // so this is for reference/copying only and is never sent back on save.
    const pathLabel = document.createElement('label');
    pathLabel.textContent = 'Path: ';
    const pathInput = document.createElement('input');
    pathInput.type = 'text';
    pathInput.id = 'editPath';
    pathInput.className = 'form-control';
    pathInput.readOnly = true;
    pathInput.value = track.path || '';  // assigning .value never parses HTML
    pathLabel.appendChild(pathInput);
    editFormContainer.appendChild(pathLabel);

    // Wire actions via closures over the track object (which carries the stable
    // id) rather than interpolating its fields into inline onclick strings.
    const actions = [
        { text: 'Remove', className: 'btn btn-warning mt-2', handler: () => confirmAction('remove', track) },
        { text: 'Delete', className: 'btn btn-danger mt-2', handler: () => confirmAction('delete', track) },
        { text: 'Save', className: 'btn btn-success mt-2', handler: () => saveTrack(track) },
        { text: 'Cancel', className: 'btn btn-secondary mt-2', handler: () => closeEditForm() },
    ];
    actions.forEach(action => {
        const button = document.createElement('button');
        button.className = action.className;
        button.textContent = action.text;
        button.addEventListener('click', action.handler);
        editFormContainer.appendChild(button);
    });
}

function saveTrack(track) {
    const updatedTrack = {
        title: document.getElementById('editTitle').value,
        artist: document.getElementById('editArtist').value,
        album: document.getElementById('editAlbum').value,
        year: document.getElementById('editYear').value,
        genre: document.getElementById('editGenre').value,
        composer: document.getElementById('editComposer').value,
        bpm: document.getElementById('editBpm').value,
        comments: document.getElementById('editComments').value,
    };

    fetch('/api/library/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        // id targets the exact track; original* stays as a server-side fallback.
        body: JSON.stringify({
            id: track.id,
            originalTitle: track.title,
            originalArtist: track.artist,
            originalAlbum: track.album,
            updatedTrack,
        }),
    })
    .then(response => response.json())
    .then(data => {
        alert(data.message || 'Track updated successfully.');
        fetchLibrary();
        closeEditForm();
    })
    .catch(error => {
        alert('Error updating track: ' + error.message);
    });
}

function confirmAction(action, track) {
    const actionText = action === 'delete' ? 'delete this track? This action cannot be undone.' : 'remove this track from the library?';
    // Remove any leftover modal (e.g. dismissed without acting) so the id stays
    // unique and the handler below targets the fresh one.
    const stale = document.getElementById('confirmationModal');
    if (stale) stale.remove();

    // actionText is a fixed string; the track fields are NOT interpolated into
    // the markup — the Confirm handler is wired via addEventListener below.
    const modalHtml = `
        <div class="modal fade" id="confirmationModal" tabindex="-1" aria-labelledby="confirmationModalLabel" aria-hidden="true">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="confirmationModalLabel">Confirm Action</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        Are you sure you want to ${actionText}
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="button" class="btn btn-danger" id="confirmActionButton">Confirm</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    document.getElementById('confirmActionButton')
        .addEventListener('click', () => executeAction(action, track));
    const confirmationModal = new bootstrap.Modal(document.getElementById('confirmationModal'));
    confirmationModal.show();
}

function executeAction(action, track) {
    const endpoint = action === 'delete' ? '/api/library/delete' : '/api/library/remove';
    fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            id: track.id,
            title: track.title,
            artist: track.artist,
            album: track.album,
        }),
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        alert(data.message || `Track ${action}d successfully.`);
        fetchLibrary();
        closeEditForm();
        document.getElementById('confirmationModal').remove();
    })
    .catch(error => {
        alert(`Error ${action}ing track: ${error.message}`);
        const modal = document.getElementById('confirmationModal');
        if (modal) modal.remove();
    });
}

function closeEditForm() {
    const editFormContainer = document.getElementById('editFormContainer');
    editFormContainer.innerHTML = '';
    editFormContainer.style.display = 'none';
}
