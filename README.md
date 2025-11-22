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
- **Pillow**: For raster exports (PNG/JPEG) and intermediate assets

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

3. Install additional dependencies for Office export features:
   ```bash
   pip install reportlab python-docx python-pptx
   ```

4. Install the OpenAI Python SDK so the Qwen-compatible client can run:
   ```bash
   pip install "openai>=1.12"
   ```

### Environment Variables

Fiona uses the following environment variables:

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
The server automatically loads `.env` on startup, so you can keep secrets locally without exporting them in your shell.

### Qwen Integration

Fyona uses Alibaba's DashScope service via the OpenAI-compatible API to power the chat assistant. When you enable **Agent Mode** the backend automatically collects the project directory tree, indexed file previews, and the latest `layout.json`, then attaches them alongside any canvas snapshots you share in chat. The `qwen3-vl-plus` model can therefore inspect:

- Your typed prompt
- A PNG capture of the current canvas
- The JSON layout definition and block metadata
- A tree plus selected file previews from the active project directory

If you additionally allow layout edits, Fyona exposes tools for reading/writing `layout.json` and for running the built-in terminal commands. The assistant will call these tools repeatedly until it reports that the task is finished or it exhausts the safety budget, letting it implement multi-step changes automatically.

The assistant responds in Markdown with layout-specific recommendations. If the DashScope credentials or the `openai` package are missing, the UI will fall back to a lightweight acknowledgement so you always know what the server received.

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
5. When Agent Mode is enabled you can toggle **Allow layout edits** inside the chat panel. Turning it on lets Fyona call built-in tools to read or overwrite `layout.json`, or to run structured terminal commands until the task is complete.

When Agent Mode is active, the assistant now iteratively replays your request: it issues precise terminal commands, re-reads the layout (or runs `status`/`echo`), restates what still needs work, and continues issuing edits until the design matches your description or it explains what remains. Each pass arrives with the latest plan, so the agent reanalyzes the problem space without you needing to resend the prompt manually. The run-mode dropdown/tool-limit counter has been removed because Fyona now always auto-continues until the layout satisfies your prompt.

### Terminal Commands

Open the floating terminal (or type `/terminal` in chat) to run scripted layout tweaks. Besides the original `pages`, `echo`, and `add` verbs, the terminal now understands:

- `status`, `pages`, `blocks --page 2 --type text` for fast layout summaries
- `move hero_title --to (128,96)`, `resize 3 --size 320x180`, `delete hero_image` for block edits
- `duplicate hero_title --offset (32,32)`, `newpage "Features" --from 2`, `renamepage 3 "Workflow"`
- `activate 4`, `deletepage 5`, and `grid --columns 8 --gutter 24 --snap on` for project-wide adjustments
The agent is explicitly taught these terminal commands, so when it runs `run_terminal_command` it can carry out the relevant operation and then re-evaluate the layout before the next step. Use the floating terminal yourself to mirror what the assistant is doing.

Full command set:
- `help` – list available terminal verbs
- `status` – report project, grid, palette, and typography details
- `pages` / `blocks` / `echo` – inspect pages, blocks, and content previews
- `move` / `resize` / `duplicate` / `delete` / `remove` – modify blocks
- `add` / `edit` / `content` / `append` / `prepend` – insert or rewrite copy
- `newpage` / `renamepage` / `deletepage` / `activate` – manage pages
- `grid` – adjust the document grid system

Every command returns a short explanation plus updates the canvas automatically when a change is made, making repetitive layout chores much faster.

### Exporting Layouts

Lossless export is powered by `pdf_export.py`, with additional format conversions handled by `export_formats.py`. Every export option renders the PDF first so the output matches what you see on the canvas.

- `render_layout_to_pdf()` converts a layout dictionary into a vector PDF and returns the bytes plus render stats (page count, block counts, and a layout digest).
- `export_layout(..., export_format=...)` wraps the PDF renderer and emits PNG, JPEG, DOCX, or PPTX by rasterizing/embedding the generated PDF. PNG/JPEG exports return a ZIP file when multiple pages are present.
- `GET /api/export/<format>?project=<name>` streams the requested asset. Supported values for `<format>`: `pdf`, `png`, `jpeg`, `docx`, `pptx`. Responses include `X-Layout-Digest`, `X-Blocks-Rendered`, `X-Blocks-Expected`, and `X-Download-Filename` headers for verification.

Example:
```bash
curl -L "http://localhost:5001/api/export/png?project=default" \
  -o default-layout.png -D -
```
Compare the digest header with a hash of `layout.json` to confirm the export is identical to the canvas.

The editor toolbar now includes an **Export as** selector plus a **Download** button. Choose PDF/PNG/JPEG/Word/PowerPoint during editing to download the current project instantly (the UI calls the same verified endpoints).

> **Optional Dependencies:** DOCX exports require `python-docx`, and PPTX exports require `python-pptx`. Install them alongside `reportlab` for the full export suite.

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
- `GET /api/export?project=:project&format=<fmt>` - Render layouts as `pdf`, `png`, `jpeg`, `docx`, or `pptx`
- `GET /api/export/<fmt>?project=:project` - Path-based alternative for the same formats

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
6. **raster_export.py**: Canvas rasterization helpers for PNG/JPEG/Office exports
7. **static/js/app.js**: Main frontend application logic
8. **templates/index.html**: Main UI layout and controls

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
