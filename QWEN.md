# Fyona Editorial Studio

## Project Overview

Fyona Editorial Studio is a web-based editorial layout application that allows users to create magazine-style layouts with AI assistance capabilities. Built with Flask (Python) on the backend and vanilla JavaScript on the frontend, Fyona provides a visual canvas for designing layouts with precise grid controls and an AI assistant powered by Qwen3-VL-Plus.

The application combines traditional layout tools with AI-powered automation through an "Agent Mode" that can interact with and modify layouts based on user instructions. The system supports multi-page document creation, precise grid controls, and export capabilities.

## Key Features

- **Visual Layout Editor**: Drag-and-drop interface for creating magazine-style layouts
- **AI Assistant Integration**: Intelligent layout suggestions and modifications using Qwen3-VL-Plus
- **Multi-page Support**: Create and manage multi-page documents with layer management
- **Precise Grid Controls**: Column-based layouts with baseline grid alignment
- **PDF Export**: Export layouts as vector or snapshot-based PDFs
- **Project Management**: Organize layouts into different projects
- **Responsive Design**: Works on various screen sizes
- **Terminal Commands**: CLI-like interface for precise layout modifications
- **Auto-continuation**: AI automatically iterates on layout improvements

## Technology Stack

### Backend
- **Flask**: Python web framework
- **OpenAI-compatible API**: For connecting to Qwen3-VL-Plus model
- **ReportLab**: For vector PDF export
- **Pillow**: For raster exports (PNG/JPEG) and intermediate assets

### Frontend
- **Vanilla JavaScript**: No framework dependencies
- **HTML5/CSS3**: For layout and styling
- **html2canvas**: For client-side screenshot capture

## Project Structure

```
Fyona/
├── app.py                 # Main Flask application
├── agent_tools.py         # Tool definitions for AI assistant
├── export_formats.py      # Export format conversion utilities
├── fonts.py               # Font management utilities
├── pdf_export.py          # PDF export functionality
├── raster_export.py       # Canvas rasterization for PNG/JPEG export
├── terminal.py            # CLI-style command processor
├── projects/              # User projects and layouts
├── static/                # Frontend assets (CSS, JS)
│   ├── css/
│   │   └── styles.css     # Main stylesheet
│   └── js/
│       └── app.js         # Main application logic
└── templates/
    └── index.html         # Main UI layout and controls
```

## Main Components

### Core Application (`app.py`)
The main Flask application with route definitions and state management. Handles:
- Project and layout persistence
- AI assistant integration
- File uploads
- PDF and other format exports
- Terminal command processing
- Token usage tracking

### AI Tools (`agent_tools.py`)
Defines the toolset available to the AI assistant for interacting with layouts:
- `read_layout_file`: Read layout.json content
- `write_layout_file`: Write layout changes
- `run_terminal_command`: Execute terminal commands
- `write_project_file`: Write text files in the project
- `list_project_files`: List project directory contents
- `read_project_file`: Read text files from project
- `search_project_files`: Search text across project files
- `save_remote_image`: Download and save images
- `web_search` / `web_image_search`: Bing search integration

### Export System (`pdf_export.py`)
Converts layout JSON to print-ready PDFs with:
- Lossless rendering that matches canvas display
- Support for text and image blocks
- Font handling and typography
- Page-by-page layout conversion
- Customizable dimensions and formats

### Terminal Commands (`terminal.py`)
Provides CLI-style interface for precise layout modifications:
- Block creation, movement, resizing
- Page management
- Grid configuration
- Content editing
- Batch operations

The assistant learns the same terminal verbs it can issue itself, including `help`, `status`, `pages`, `echo`, `blocks`, `move`, `resize`, `duplicate`, `delete`, `remove`, `newpage`, `renamepage`, `deletepage`, `activate`, `grid`, `add`, `edit`, `content`, `append`, and `prepend`. When Agent Mode is authorized to edit, Fyona keeps re-running terminal commands, re-reading the layout, and rephrasing the original request between passes so it can address the next area of improvement until the layout matches the prompt or it summarizes what remains.

## API Endpoints

### Layout Management
- `GET /api/layout?project=:project` - Retrieve current layout
- `POST /api/layout` - Save layout data
- `GET /api/projects` - List available projects

### Block Operations
- `POST /api/block` - Add, update, or delete blocks

### Media Handling
- `POST /api/upload` - Upload images

### Document Export
- `GET /api/export?project=:project&format=<fmt>` - Export layouts as PDF, PNG, JPEG, DOCX, or PPTX
- `GET /api/export/<fmt>?project=:project` - Path-based export endpoints

### AI Assistant
- `POST /api/chat` - Run AI assistant with various modes and permissions
- `POST /api/chat/attachments/canvas` - Generate canvas preview as attachment
- `GET /api/chat/agent-snapshot` - Get project snapshot for AI context
- `GET /api/chat/progress/<progress_id>` - Check agent progress
- `GET /api/chat/token-stats` - Get token usage statistics

### Terminal
- `POST /api/terminal` - Execute terminal commands

## Qwen AI Integration

The application integrates with Alibaba's DashScope service via the OpenAI-compatible API to power the chat assistant. When Agent Mode is enabled, the backend automatically collects:
- Project directory tree
- Indexed file previews
- Current layout.json
- Canvas snapshots

The assistant can then make layout modifications using the available tools when authorized, implementing multi-step changes automatically until the task is complete or the safety budget is exhausted.

## Building and Running

### Prerequisites

- Python 3.10+
- pip (Python package installer)

### Installation

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Install additional dependencies for Office export features:
   ```bash
   pip install reportlab python-docx python-pptx
   ```

3. Install the OpenAI Python SDK so the Qwen-compatible client can run:
   ```bash
   pip install "openai>=1.12"
   ```

### Environment Variables

Fyona uses the following environment variables:

- `DASHSCOPE_API_KEY`: API key for DashScope (required for AI features)
- `DASHSCOPE_BASE_URL`: Base URL for DashScope API (optional, defaults to official endpoint)
- `FIONA_AGENT_MODEL`: Model to use for AI assistant (optional, defaults to `qwen3-vl-plus`)
- `FIONA_AGENT_ENABLE_THINKING`: Set to `true` to enable Qwen's reasoning trace (optional, defaults to `false`)
- `FIONA_AGENT_THINKING_BUDGET`: Max reasoning tokens when thinking mode is enabled (optional, defaults to `81920`)

You can set these in a `.env` file in the project root:
```bash
DASHSCOPE_API_KEY=your_api_key_here
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
FIONA_AGENT_MODEL=qwen3-vl-plus
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

## Development Conventions

- The backend follows Flask patterns with route handlers in `app.py`
- Layout state management is in memory with file-based persistence for projects
- Modular tool system for AI integration
- Frontend uses event-driven architecture with state management in the `state` object
- Component-based UI with reusable functions
- CSS variables for dynamic styling

## Export Functionality

The export system works by:
1. Rendering the layout as a vector PDF using `pdf_export.py`
2. Converting the PDF to other formats (PNG, JPEG, DOCX, PPTX) using `export_formats.py`
3. Streaming the requested asset via API endpoints
4. Including verification headers for export integrity

## Auto-continuation Feature

The AI assistant supports an auto-continuation mode that:
- Runs the AI agent in iterative cycles
- Evaluates the current layout state after each iteration
- Continues until the layout is satisfactory or max iterations reached
- Provides follow-up suggestions
- Tracks token usage and progress

## Terminal Commands

The terminal system supports various commands for layout manipulation:
- `add` - Add text/image blocks
- `move` - Move blocks to new positions
- `resize` - Change block dimensions
- `duplicate` - Copy blocks with optional offset
- `delete` - Remove blocks
- `newpage` - Create new pages
- `renamepage` - Rename existing pages
- `grid` - Configure grid settings
- `pages` / `echo` - List pages and blocks
- `edit` - Modify block properties
- `content` / `append` / `prepend` - Update text content

## Project Management

Projects are stored in the `projects/` directory with the following structure:
- Each project has its own folder
- Contains a `layout.json` file with the layout data
- Contains a `media/` subfolder for uploaded assets
- Each project has an `exports/` subfolder for generated exports

## Security and Permissions

The AI assistant has a permission system with:
- `allow_layout_edits` - Allows AI to modify layout files
- `allow_web_search` - Enables Bing search capabilities
- Tool budget limits to prevent excessive API usage
- Safe path resolution to prevent directory traversal
- Input validation and sanitization

## Error Handling

- API endpoints return appropriate HTTP status codes
- Validation and error handling for all user inputs
- Graceful fallback when external services are unavailable
- Detailed error messages for debugging

## Testing

The application includes comprehensive error handling and validation for:
- Invalid JSON layouts
- Unauthorized file operations
- Network request failures
- Unsupported export formats
- Invalid command parameters
- Malformed input data
- Missing dependencies
