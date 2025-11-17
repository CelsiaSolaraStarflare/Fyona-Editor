#!/usr/bin/env python3
"""
Fyona Canvas Editor - Minimal Flask Application

This is a minimal Flask application for the Fyona Canvas Editor.
"""

from flask import Flask, render_template, jsonify, request
import json
import os
import uuid

# Create Flask app
app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')

# In-memory storage for layouts (in production, you would use a database)
layouts = {}

# Routes
@app.route('/')
def index():
    """Serve the main canvas editor page"""
    return render_template('index.html')

@app.route('/api/layout', methods=['GET', 'POST'])
def layout_api():
    """Handle layout operations"""
    global layouts
    
    if request.method == 'GET':
        # Return current layout or default
        project = request.args.get('project', 'default')
        layout = layouts.get(project, get_default_layout())
        return jsonify(layout)
    
    else:  # POST
        # Save layout
        data = request.get_json() or {}
        project = data.get('project', 'default')
        layouts[project] = data.get('layout', {})
        return jsonify({'success': True})

@app.route('/api/block', methods=['POST'])
def block_api():
    """Handle block operations"""
    global layouts
    
    data = request.get_json() or {}
    project = data.get('project', 'default')
    operation = data.get('operation')
    
    # Get or create layout for project
    if project not in layouts:
        layouts[project] = get_default_layout()
    
    layout = layouts[project]
    
    if operation == 'add':
        # Add a new block
        block = data.get('block', {})
        if 'id' not in block:
            block['id'] = f'block-{uuid.uuid4().hex[:8]}'
        
        layout['blocks'].append(block)
        return jsonify({'success': True, 'block': block})
    
    elif operation == 'update':
        # Update an existing block
        block_id = data.get('block_id')
        updates = data.get('updates', {})
        
        for block in layout['blocks']:
            if block['id'] == block_id:
                block.update(updates)
                return jsonify({'success': True, 'block': block})
        
        return jsonify({'success': False, 'error': 'Block not found'})
    
    elif operation == 'delete':
        # Delete a block
        block_id = data.get('block_id')
        layout['blocks'] = [b for b in layout['blocks'] if b['id'] != block_id]
        return jsonify({'success': True})
    
    else:
        return jsonify({'success': False, 'error': 'Invalid operation'})

def get_default_layout():
    """Create a default layout"""
    return {
        'columns': 3,
        'baseline': 24,
        'gutter': 32,
        'snap': True,
        'zoom': 1.0,
        'orientation': 'portrait',
        'format': 'A4',
        'dimensions': {'width': 794, 'height': 1123},
        'blocks': [],
        'layers': [
            {
                'id': 'layer-main',
                'name': 'Layer 1',
                'order': 0,
            }
        ],
        'activeLayer': 'layer-main'
    }

if __name__ == '__main__':
    app.run(debug=True, port=5001)