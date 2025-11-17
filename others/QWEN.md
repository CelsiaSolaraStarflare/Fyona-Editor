# Fiona Editorial Studio - Project Context

## Project Overview

Fiona is a web-based editorial layout studio built with Flask (Python) on the backend and vanilla JavaScript on the frontend. It provides a visual canvas for creating magazine-style layouts with AI assistance capabilities. The application allows users to design multi-page layouts with blocks (text, images, etc.), layers, and precise grid controls.

Key features include:
- Visual layout editor with drag-and-drop blocks
- AI assistant integration with vision capabilities (using Qwen3-VL-Plus)
- Time Machine functionality for version control via Git
- PDF export capabilities (both vector and snapshot-based)
- Multi-page support with layer management
- Responsive design tools with precise grid controls

## Technology Stack

### Backend
- **Flask** - Python web framework
- **OpenAI-compatible API** - For connecting to Qwen3-VL-Plus model
- **Git** - For Time Machine version control
- **ReportLab** - For vector PDF export
- **PyMuPDF (fitz)** - For snapshot-based PDF export
- **Pillow** - For image processing and snapshots

### Frontend
- **Vanilla JavaScript** - No framework dependencies
- **HTML5/CSS3** - For layout and styling
- **Liquid Glass effect** - Custom visual effects (both vanilla JS and React versions available)
- **html2canvas** - For client-side screenshot capture
- **jsPDF** - For PDF generation

## Project Structure

```
Fiona/
├── app.py                 # Main Flask application
├── core.py                # AI chat functionality
├── agent_tools.py         # Tool definitions for AI assistant
├── snapshot.py            # Layout snapshot generation
├── pdf_export.py          # PDF export functionality
├── requirements.txt       # Python dependencies
├── state/                 # User data and layouts
├── static/                # Frontend assets (CSS, JS)
│   ├── css/
│   │   └── styles.css     # Main stylesheet
│   └── js/
│       ├── app.js         # Main application logic
│       └── src/           # Modular JavaScript components
```

## Core Functionality

### Layout Editor
The main interface allows users to:
- Create and edit multi-page layouts
- Add various block types (headline, body, image, pullquote, etc.)
- Manage layers for organizing content
- Use precise grid controls for alignment
- Apply typography and styling options

### AI Assistant
The AI assistant uses Qwen3-VL-Plus to:
- Understand layout context through visual snapshots
- Execute tool calls to modify layouts
- Provide reasoning and answers to user queries
- Support both local and remote model modes

### Time Machine
Version control system using Git to:
- Automatically commit layout changes
- Browse historical snapshots
- Revert to previous versions

### Export
Multiple export options:
- PDF export (vector-based using ReportLab)
- PDF export (snapshot-based using PyMuPDF)
- JSON export of layout data

## Development Setup

### Prerequisites
- Python 3.10+
- Node.js (for Liquid Glass React development)
- Git (for Time Machine functionality)

### Installation
1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. For PDF export functionality, ensure ReportLab is available:
   ```bash
   pip install reportlab
   ```

3. For snapshot-based PDF export, install PyMuPDF:
   ```bash
   pip install PyMuPDF
   ```

### Running the Application
```bash
python app.py
```
The application will start on http://localhost:5001

## Key APIs

### Layout Management
- `GET /layout` - Retrieve current layout
- `POST /save-layout` - Save layout data
- `GET /projects` - List available projects
- `GET /demo-layout` - Load demo layout

### AI Assistant
- `POST /api/assistant/chat` - Send message to AI assistant

### Time Machine
- `POST /time-machine/snapshot` - Create snapshot
- `GET /time-machine/history` - Get snapshot history
- `POST /time-machine/revert` - Revert to snapshot

### Export
- `POST /export/pdf` - Export layout as PDF

### Settings
- `GET /api/settings` - Get application settings
- `POST /api/settings` - Update application settings

## Development Conventions

### Backend
- Follow Flask patterns for route handling
- Use type hints for function parameters and return values
- Maintain consistent error handling with JSON responses
- Use logging for debugging and monitoring

### Frontend
- Modular JavaScript organization in static/js/src/
- CSS follows BEM naming conventions
- Template-based HTML structure
- Event-driven architecture for UI interactions

### AI Tool Integration
- Tools are defined in `agent_tools.py`
- Each tool has a specific handler in `LayoutSession` class
- Tool events are tracked for UI feedback
- Layout mutations are tracked for auto-application

## Building and Running

### Development
```bash
python app.py
```

### Production
For production deployment, use Gunicorn:
```bash
gunicorn -w 4 -b 0.0.0.0:5001 app:app
```

### Testing
Currently, there are no automated tests. Manual testing through the UI is recommended.

## Contributing

1. Follow the existing code style and conventions
2. Add type hints to new Python functions
3. Maintain backward compatibility when possible
4. Update documentation when adding new features
5. Test changes thoroughly before submitting

## Key Files to Understand the Codebase

1. **app.py** - Main application entry point and route definitions
2. **core.py** - AI chat functionality and model integration
3. **agent_tools.py** - Tool definitions and layout mutation handlers
4. **snapshot.py** - Layout snapshot generation for AI context
5. **pdf_export.py** - PDF export functionality
6. **templates/index.html** - Main UI layout and controls
7. **static/js/app.js** - Main frontend application logic