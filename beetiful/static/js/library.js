document.addEventListener('DOMContentLoaded', () => {
    fetchLibrary();
});

let currentPage = 1;
const itemsPerPage = 20;
let libraryData = [];
let filteredData = [];
let sortOrder = { column: null, direction: 'asc' };

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
                libraryData = data.items;
                filteredData = libraryData;
                showPage(currentPage);
            } else {
                console.error('Unexpected data format:', data);
                document.getElementById('libraryResults').innerHTML = '<tr><td colspan="5">No library data found.</td></tr>';
            }
        })
        .catch(error => {
            console.error('Error fetching library data:', error);
            document.getElementById('libraryResults').innerHTML = '<tr><td colspan="5">Error loading library data.</td></tr>';
        });
}

// When no beets library exists, show a focused notice and hide the table,
// filters and pagination so the user's only next action is clear.
function showNoLibraryNotice(info) {
    const tableContainer = document.querySelector('.table-container');
    if (tableContainer) tableContainer.style.display = 'none';
    const pagination = document.getElementById('paginationControls');
    if (pagination) pagination.style.display = 'none';
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
    const pagination = document.getElementById('paginationControls');
    if (pagination) pagination.style.display = '';
}


function showPage(page) {
    const start = (page - 1) * itemsPerPage;
    const end = start + itemsPerPage;
    const itemsToDisplay = filteredData.slice(start, end);

    populateLibrary(itemsToDisplay);
    updatePaginationControls();
}


function applyFilters() {
    const filterTitle = document.getElementById('filterTitle').value.toLowerCase();
    const filterArtist = document.getElementById('filterArtist').value.toLowerCase();
    const filterAlbum = document.getElementById('filterAlbum').value.toLowerCase();
    const filterGenre = document.getElementById('filterGenre').value.toLowerCase();

    filteredData = libraryData.filter(item => {
        return (
            (!filterTitle || item.title.toLowerCase().includes(filterTitle)) &&
            (!filterArtist || item.artist.toLowerCase().includes(filterArtist)) &&
            (!filterAlbum || item.album.toLowerCase().includes(filterAlbum)) &&
            (!filterGenre || item.genre.toLowerCase().includes(filterGenre))
        );
    });

    
    document.querySelectorAll('th').forEach(th => th.classList.remove('asc', 'desc'));
    sortOrder = { column: null, direction: 'asc' };

    currentPage = 1; 
    showPage(currentPage);
}

function clearFilters() {
    
    document.getElementById('filterTitle').value = '';
    document.getElementById('filterArtist').value = '';
    document.getElementById('filterAlbum').value = '';
    document.getElementById('filterGenre').value = '';

    
    applyFilters();
}



document.querySelectorAll('.filter-input').forEach(input => {
    input.addEventListener('input', () => {
        applyFilters();
    });
});
function sortByColumn(column) {
    
    document.querySelectorAll('#tableHeaders th').forEach(th => {
        th.classList.remove('asc', 'desc');
        th.querySelector('.sort-arrow')?.remove(); 
    });

    
    if (sortOrder.column === column) {
        sortOrder.direction = sortOrder.direction === 'asc' ? 'desc' : 'asc';
    } else {
        sortOrder.column = column;
        sortOrder.direction = 'asc';
    }

    
    filteredData.sort((a, b) => {
        const aValue = a[column]?.toLowerCase() || '';
        const bValue = b[column]?.toLowerCase() || '';

        if (aValue < bValue) return sortOrder.direction === 'asc' ? -1 : 1;
        if (aValue > bValue) return sortOrder.direction === 'asc' ? 1 : -1;
        return 0;
    });

    
    const header = document.querySelector(`#tableHeaders th[data-column="${column}"]`);
    header.classList.add(sortOrder.direction); 
    const arrow = document.createElement('span');
    arrow.className = 'sort-arrow';
    arrow.innerHTML = sortOrder.direction === 'asc' ? '▲' : '▼';
    header.appendChild(arrow);

    showPage(currentPage); 
}







function updatePaginationControls() {
    const totalPages = Math.ceil(filteredData.length / itemsPerPage);
    const paginationControls = document.getElementById('paginationControls');
    paginationControls.innerHTML = '';

    const firstButton = document.createElement('button');
    firstButton.innerText = 'First';
    firstButton.disabled = currentPage === 1;
    firstButton.onclick = () => {
        currentPage = 1;
        showPage(currentPage);
    };
    paginationControls.appendChild(firstButton);

    const prevButton = document.createElement('button');
    prevButton.innerText = 'Previous';
    prevButton.disabled = currentPage === 1;
    prevButton.onclick = () => {
        if (currentPage > 1) {
            currentPage--;
            showPage(currentPage);
        }
    };
    paginationControls.appendChild(prevButton);

    
    const maxButtons = 5;
    const startPage = Math.max(1, currentPage - Math.floor(maxButtons / 2));
    const endPage = Math.min(totalPages, startPage + maxButtons - 1);

    for (let i = startPage; i <= endPage; i++) {
        const pageButton = document.createElement('button');
        pageButton.innerText = i;
        pageButton.disabled = i === currentPage;
        pageButton.classList.toggle('active-page', i === currentPage); 
        pageButton.onclick = () => {
            currentPage = i;
            showPage(currentPage);
        };
        paginationControls.appendChild(pageButton);
    }

    const nextButton = document.createElement('button');
    nextButton.innerText = 'Next';
    nextButton.disabled = currentPage === totalPages;
    nextButton.onclick = () => {
        if (currentPage < totalPages) {
            currentPage++;
            showPage(currentPage);
        }
    };
    paginationControls.appendChild(nextButton);

    const lastButton = document.createElement('button');
    lastButton.innerText = 'Last';
    lastButton.disabled = currentPage === totalPages;
    lastButton.onclick = () => {
        currentPage = totalPages;
        showPage(currentPage);
    };
    paginationControls.appendChild(lastButton);

    const pageInfo = document.createElement('span');
    pageInfo.innerText = ` Page ${currentPage} of ${totalPages} `;
    paginationControls.appendChild(pageInfo);
}




document.getElementById('tableHeaders').addEventListener('click', (event) => {
    const column = event.target.dataset.column;
    if (column !== undefined) {
        sortByColumn(column);
    }
});
function populateLibrary(items) {
    const libraryResults = document.getElementById('libraryResults');
    libraryResults.innerHTML = '';

    items.forEach(item => {
        const row = document.createElement('tr');

        // Use textContent so track metadata is never parsed as HTML (stored XSS).
        ['title', 'artist', 'album', 'genre'].forEach(field => {
            const cell = document.createElement('td');
            cell.textContent = item[field] || '';
            row.appendChild(cell);
        });

        const actionCell = document.createElement('td');
        const editButton = document.createElement('button');
        editButton.className = 'btn btn-primary btn-sm';
        editButton.textContent = 'Edit';
        // Pass the item via a closure instead of serializing it into markup.
        editButton.addEventListener('click', () => editTrack(item));
        actionCell.appendChild(editButton);
        row.appendChild(actionCell);

        libraryResults.appendChild(row);
    });
}

function editTrack(track) {
    const editFormContainer = document.getElementById('editFormContainer');
    editFormContainer.innerHTML = '';

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

    // Wire actions via closures over the track object rather than interpolating
    // its fields into inline onclick strings.
    const actions = [
        { text: 'Remove', className: 'btn btn-warning mt-2', handler: () => confirmAction('remove', track.title, track.artist, track.album) },
        { text: 'Delete', className: 'btn btn-danger mt-2', handler: () => confirmAction('delete', track.title, track.artist, track.album) },
        { text: 'Save', className: 'btn btn-success mt-2', handler: () => saveTrack(track.title, track.artist, track.album) },
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

function saveTrack(originalTitle, originalArtist, originalAlbum) {
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
        body: JSON.stringify({ originalTitle, originalArtist, originalAlbum, updatedTrack })
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

function removeTrack(title, artist, album) {
    if (!confirm('Are you sure you want to remove this track from the library?')) return;

    fetch('/api/library/remove', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, artist, album })
    })
    .then(response => response.json())
    .then(data => {
        console.log('Remove response:', data);
        if (data.message) {
            alert(data.message || 'Track removed successfully.');
        } else {
            alert('Failed to remove track: ' + (data.error || 'Unknown error.'));
        }
        fetchLibrary();  
        closeEditForm();
    })
    .catch(error => {
        console.error('Error removing track:', error);
        alert('Error removing track: ' + error.message);
    });
}

function deleteTrack(title, artist, album) {
    if (!confirm('Are you sure you want to delete this track? This action cannot be undone.')) return;

    fetch('/api/library/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, artist, album })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        console.log('Delete response:', data);
        if (data.message) {
            alert(data.message || 'Track deleted successfully.');
        } else {
            alert('Failed to delete track: ' + (data.error || 'Unknown error.'));
        }
        fetchLibrary();  
        closeEditForm(); 
    })
    .catch(error => {
        console.error('Error deleting track:', error);
        alert('Error deleting track: ' + error.message);
    });
}


function closeEditForm() {
    const editFormContainer = document.getElementById('editFormContainer');
    editFormContainer.innerHTML = '';  
    editFormContainer.style.display = 'none';  
}





function confirmAction(action, title, artist, album) {
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
        .addEventListener('click', () => executeAction(action, title, artist, album));
    const confirmationModal = new bootstrap.Modal(document.getElementById('confirmationModal'));
    confirmationModal.show();
}

function executeAction(action, title, artist, album) {
    const endpoint = action === 'delete' ? '/api/library/delete' : '/api/library/remove';
    fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, artist, album })
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
        document.getElementById('confirmationModal').remove();
    });
}