# Fyona Editorial Studio
![PA Logo on Ofiicial Accounts](https://github.com/user-attachments/assets/decb9d1a-5d95-4bc5-9117-7150110f8c97)

Fiona is a web-based editorial layout studio that allows users to create magazine-style layouts by hand. Built with Flask (Python) on the backend and vanilla JavaScript on the frontend, Fiona provides a visual canvas for designing layouts with precise grid controls.

## Key Features

- **Visual Layout Editor**: Drag-and-drop interface for creating magazine-style layouts
- **Multi-page Support**: Create and manage multi-page documents with layer management
- **Precise Grid Controls**: Column-based layouts with baseline grid alignment
- **PDF Export**: Export layouts as vector or snapshot-based PDFs
- **Project Management**: Organize layouts into different projects
- **Responsive Design**: Works on various screen sizes

## Technology Stack

### Backend
- **Flask**: Python web framework
- **ReportLab**: For vector PDF export
- **PyMuPDF (fitz)**: For snapshot-based PDF export
- **Pillow**: For image processing and snapshots

### Frontend
- **Vanilla JavaScript**: No framework dependencies
- **HTML5/CSS3**: For layout and styling

## Project Structure

```
Fiona/
├── app.py                 # Main Flask application
├── snapshot.py            # Layout snapshot helpers
├── others/                # Additional documentation
├── projects/              # User projects and layouts
├── static/                # Frontend assets (CSS, JS)
│   ├── css/
│   │   └── styles.css     # Main stylesheet
│   └── js/
│       └── app.js         # Main application logic
└── templates/
    └── index.html         # Main UI layout and controls
```

## Getting Started

### Prerequisites

- Python 3.10+
- pip (Python package installer)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/fyona/fyona.git
   cd fyona
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Install additional dependencies for PDF export:
   ```bash
   pip install reportlab PyMuPDF
   ```

### Environment Variables

No additional environment variables are required for the standard editor workflow.

### Running the Application

During development:
```bash
python app.py
```

For production deployment:
```bash
gunicorn -w 4 -b 0.0.0.0:5001 app:app
```

The application will be available at `http://localhost:5001`.

## Usage

### Creating Layouts

1. Open the application in your browser
2. Select a project or create a new one
3. Add text or image blocks using the toolbar buttons
4. Drag and resize blocks to arrange your layout
5. Customize block properties in the inspector panel

### Exporting to PDF

PDF export functionality is available through the API endpoints:
- Vector-based export using ReportLab
- Snapshot-based export using PyMuPDF

## API Endpoints

### Layout Management
- `GET /api/layout?project=:project` - Retrieve current layout
- `POST /api/layout` - Save layout data
- `GET /api/projects` - List available projects

### Block Operations
- `POST /api/block` - Add, update, or delete blocks

### Media Handling
- `POST /api/upload` - Upload images

## Development

### Code Structure

The main components of the application are:

1. **app.py**: Flask application with route definitions
2. **snapshot.py**: Layout snapshot helpers
3. **static/js/app.js**: Main frontend application logic
4. **templates/index.html**: Main UI layout and controls
5. **others/**: Additional documentation and references

### Frontend Architecture

The frontend is built with vanilla JavaScript and follows these patterns:

- Event-driven architecture
- State management in the `state` object
- Component-based UI with reusable functions
- CSS variables for dynamic styling

### Backend Architecture

The backend follows Flask patterns:

- Route handlers in app.py
- Layout state management in memory
- File-based persistence for projects
- Helper modules for snapshot/export utilities

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Update documentation
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Inspired by professional editorial design tools
