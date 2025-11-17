# Fiona Editorial Studio - Project Context

## Project Overview
Fiona is a web-based editorial layout studio built with Flask and vanilla JavaScript. It provides a visual canvas for creating magazine-style layouts with text and image blocks, precise grid controls, and an inspector for fine-tuning block properties.

> **Note:** The autonomous AI agent that previously shipped with Fiona has been removed. The application now focuses exclusively on the manual layout editor experience.

Key features include:
- Visual layout editor with drag-and-drop block manipulation
- Precise canvas controls (format, orientation, zoom, snapping)
- Project management backed by simple JSON files
- Media upload pipeline scoped to each project
- Snapshot helpers for exports via `snapshot.py`
- Responsive inspector for editing block content and styling

## Technology Stack

### Backend
- **Flask** – Python web framework used for routing and JSON APIs
- **Python standard library** – `json`, `pathlib`, `uuid`, and friends for persistence utilities
- **Pillow / PyMuPDF (optional)** – Used by `snapshot.py` for snapshot or PDF helpers when enabled

### Frontend
- **Vanilla JavaScript** – Single-page controller contained in `static/js/app.js`
- **HTML5 & CSS3** – Layout shell defined in `templates/index.html` and styled via `static/css/styles.css`

## Project Structure
```
Fiona/
├── app.py                 # Flask application and API routes
├── snapshot.py            # Snapshot helpers for exports
├── others/                # Additional documentation and resources
├── projects/              # Per-project layout JSON and media folders
├── static/
│   ├── css/styles.css     # Main stylesheet
│   └── js/app.js          # Browser application logic
└── templates/index.html   # UI markup for the editor
```

## Core Functionality

### Layout Editor
- Layouts consist of ordered blocks with geometry, content, and styling metadata.
- The frontend keeps a `state` object in sync with the DOM and the persisted layout JSON.
- Users can create text or image blocks, drag/resize them, and edit properties through the inspector.

### Media Pipeline
- `/api/upload` accepts file uploads scoped to a project and optional block.
- Uploaded assets are stored under `projects/<project>/media/` and linked back to the relevant block.

### Persistence
- Layouts live as `projects/<project>/layout.json` files.
- `/api/layout` (GET/POST) loads or saves full layouts after normalization on the server.
- `/api/block` handles granular block mutations (create/update/delete) without re-uploading the entire layout.

### Snapshot & Export Helpers
- The optional utilities in `snapshot.py` produce canvas snapshots or PDFs for export workflows.
- These helpers are decoupled from the main app and can be invoked from scripts or future routes.

## Development Setup

### Prerequisites
- Python 3.10+
- `pip` for dependency management

### Installation
```bash
pip install -r others/requirements.txt
```
The requirements file lists Flask and the optional imaging libraries. Install only what you need for your workflow.

### Running the Application
```bash
python app.py
```
The development server listens on `http://localhost:5001`.

### Environment Variables
No special environment variables are required for the manual editor flow.

## Key APIs
- `GET /api/projects` – List available projects
- `GET /api/layout?project=:id` – Load a project's layout
- `POST /api/layout` – Persist a full layout payload
- `POST /api/block` – Create, update, or delete a single block
- `POST /api/upload` – Upload media files scoped to a project (and optionally a block)

## Development Conventions

### Backend
- Keep route handlers in `app.py` small and focused on validation/persistence.
- Normalize incoming block/layout payloads before writing to disk.
- Prefer helper functions in `snapshot.py` for any image/PDF exports.

### Frontend
- Maintain all DOM references inside the `els` map at the top of `static/js/app.js`.
- Use the shared `state` object to coordinate canvas rendering, inspector updates, and selection.
- Avoid framework dependencies—everything is plain DOM + CSS Variables.

## Contributing
1. Fork the repository
2. Create a feature branch
3. Make and test your changes
4. Update documentation if you add new capabilities
5. Submit a pull request
