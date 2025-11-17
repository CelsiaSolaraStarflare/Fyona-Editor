# Fyona Editorial Studio
![PA Logo on Ofiicial Accounts](https://github.com/user-attachments/assets/decb9d1a-5d95-4bc5-9117-7150110f8c97)

Fiona is a web-based editorial layout studio that allows users to create magazine-style layouts with AI assistance capabilities. Built with Flask (Python) on the backend and vanilla JavaScript on the frontend, Fiona provides a visual canvas for designing layouts with precise grid controls and an AI assistant powered by Qwen3-VL-Plus.

## Key Features

- **Visual Layout Editor**: Drag-and-drop interface for creating magazine-style layouts
- **AI Assistant Integration**: Intelligent layout suggestions and modifications using Qwen3-VL-Plus
- **Multi-page Support**: Create and manage multi-page documents with layer management
- **Precise Grid Controls**: Column-based layouts with baseline grid alignment
- **PDF Export**: Export layouts as vector or snapshot-based PDFs
- **Project Management**: Organize layouts into different projects
- **Responsive Design**: Works on various screen sizes

## Technology Stack

### Backend
- **Flask**: Python web framework
- **OpenAI-compatible API**: For connecting to Qwen3-VL-Plus model
- **ReportLab**: For vector PDF export
- **PyMuPDF (fitz)**: For snapshot-based PDF export
- **Pillow**: For image processing and snapshots

### Frontend
- **Vanilla JavaScript**: No framework dependencies
- **HTML5/CSS3**: For layout and styling
- **html2canvas**: For client-side screenshot capture

## Project Structure

```
Fiona/
├── app.py                 # Main Flask application
├── core.py                # AI chat functionality
├── agent_tools.py         # Tool definitions for AI assistant
├── snapshot.py            # Layout snapshot generation
├── pdf_export.py          # PDF export functionality
├── requirements.txt       # Python dependencies
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

Fiona uses the following environment variables:

- `DASHSCOPE_API_KEY`: API key for DashScope (required for AI features)
- `DASHSCOPE_BASE_URL`: Base URL for DashScope API (optional, defaults to official endpoint)
- `FIONA_AGENT_MODEL`: Model to use for AI assistant (optional, defaults to qvq-plus)

You can set these in a `.env` file in the project root:
```bash
DASHSCOPE_API_KEY=your_api_key_here
```

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

### Using the AI Assistant

1. Click the "Agent Mode" button in the inspector panel
2. Enter a prompt describing the changes you'd like
3. Click "Run Agent" to execute the AI assistant
4. The agent will analyze your layout and make suggestions or modifications

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

### AI Assistant
- `POST /api/agent/run` - Run the AI assistant

## Development

### Code Structure

The main components of the application are:

1. **app.py**: Flask application with route definitions
2. **core.py**: AI chat functionality and model integration
3. **agent_tools.py**: Tool definitions and layout mutation handlers
4. **snapshot.py**: Layout snapshot generation for AI context
5. **pdf_export.py**: PDF export functionality
6. **static/js/app.js**: Main frontend application logic
7. **templates/index.html**: Main UI layout and controls

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
- Modular tool system for AI integration

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

- Thanks to DashScope for providing the Qwen3-VL-Plus model
- Inspired by professional editorial design tools
