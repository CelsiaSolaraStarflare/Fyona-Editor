// Main JavaScript file for Fyona Canvas Editor

document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const canvas = document.getElementById('canvas');
    const addTextBtn = document.getElementById('add-text');
    const addImageBtn = document.getElementById('add-image');
    const saveLayoutBtn = document.getElementById('save-layout');
    const loadLayoutBtn = document.getElementById('load-layout');
    
    // State
    let selectedBlock = null;
    let isDragging = false;
    let isResizing = false;
    let dragStartX, dragStartY;
    let originalX, originalY;
    let originalWidth, originalHeight;
    
    // Initialize the application
    function initApp() {
        setupEventListeners();
        loadLayout();
    }
    
    // Set up event listeners
    function setupEventListeners() {
        // Toolbar buttons
        addTextBtn.addEventListener('click', () => addBlock('text'));
        addImageBtn.addEventListener('click', () => addBlock('image'));
        saveLayoutBtn.addEventListener('click', saveLayout);
        loadLayoutBtn.addEventListener('click', loadLayout);
        
        // Canvas events
        canvas.addEventListener('click', handleCanvasClick);
        canvas.addEventListener('mousedown', handleMouseDown);
        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', handleMouseUp);
    }
    
    // Add a new block to the canvas
    function addBlock(type) {
        const block = document.createElement('div');
        const id = 'block-' + Date.now();
        
        block.className = `block ${type}`;
        block.id = id;
        block.innerHTML = type === 'text' ? 'Sample Text' : '[Image]';
        
        // Position the block
        const rect = canvas.getBoundingClientRect();
        block.style.left = '100px';
        block.style.top = '100px';
        block.style.width = type === 'text' ? '200px' : '150px';
        block.style.height = type === 'text' ? '100px' : '150px';
        
        // Add resize handle for text blocks
        if (type === 'text') {
            const resizeHandle = document.createElement('div');
            resizeHandle.className = 'resize-handle';
            block.appendChild(resizeHandle);
        }
        
        canvas.appendChild(block);
        
        // Add event listeners to the new block
        block.addEventListener('click', (e) => {
            e.stopPropagation();
            selectBlock(block);
        });
        
        // Add resize functionality
        if (type === 'text') {
            const resizeHandle = block.querySelector('.resize-handle');
            resizeHandle.addEventListener('mousedown', (e) => {
                e.stopPropagation();
                startResizing(e, block);
            });
        }
    }
    
    // Handle canvas click
    function handleCanvasClick(e) {
        // Deselect block when clicking on canvas
        if (selectedBlock) {
            deselectBlock();
        }
    }
    
    // Select a block
    function selectBlock(block) {
        // Deselect previous block
        if (selectedBlock) {
            deselectBlock();
        }
        
        // Select new block
        selectedBlock = block;
        block.classList.add('selected');
    }
    
    // Deselect current block
    function deselectBlock() {
        if (selectedBlock) {
            selectedBlock.classList.remove('selected');
            selectedBlock = null;
        }
    }
    
    // Handle mouse down on block
    function handleMouseDown(e) {
        if (e.target.classList.contains('block') && !e.target.classList.contains('resize-handle')) {
            e.stopPropagation();
            
            isDragging = true;
            selectedBlock = e.target;
            selectBlock(selectedBlock);
            
            const rect = selectedBlock.getBoundingClientRect();
            dragStartX = e.clientX;
            dragStartY = e.clientY;
            originalX = rect.left - canvas.getBoundingClientRect().left;
            originalY = rect.top - canvas.getBoundingClientRect().top;
        }
    }
    
    // Handle mouse move (handles both dragging and resizing)
    function handleMouseMove(e) {
        if (isDragging && selectedBlock && !isResizing) {
            // Handle block dragging
            const dx = e.clientX - dragStartX;
            const dy = e.clientY - dragStartY;
            
            selectedBlock.style.left = (originalX + dx) + 'px';
            selectedBlock.style.top = (originalY + dy) + 'px';
        } else if (isResizing && selectedBlock) {
            // Handle block resizing
            const dx = e.clientX - dragStartX;
            const dy = e.clientY - dragStartY;
            
            // Ensure minimum size
            const newWidth = Math.max(50, originalWidth + dx);
            const newHeight = Math.max(30, originalHeight + dy);
            
            selectedBlock.style.width = newWidth + 'px';
            selectedBlock.style.height = newHeight + 'px';
        }
    }
    
    // Handle mouse up
    function handleMouseUp() {
        isDragging = false;
        isResizing = false;
    }
    
    // Start resizing a block
    function startResizing(e, block) {
        e.stopPropagation();
        
        isResizing = true;
        isDragging = false;  // Make sure dragging is off when resizing
        selectedBlock = block;
        selectBlock(selectedBlock);
        
        const rect = selectedBlock.getBoundingClientRect();
        dragStartX = e.clientX;
        dragStartY = e.clientY;
        originalWidth = rect.width;
        originalHeight = rect.height;
        
        // Remove the separate event listeners since we're using the main ones
    }
    
    // Save layout to server
    async function saveLayout() {
        try {
            const layout = serializeLayout();
            const response = await fetch('/api/layout', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ layout })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            alert('Layout saved successfully!');
        } catch (error) {
            console.error('Error saving layout:', error);
            alert('Failed to save layout');
        }
    }
    
    // Load layout from server
    async function loadLayout() {
        try {
            const response = await fetch('/api/layout');
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            applyLayout(data);
        } catch (error) {
            console.error('Error loading layout:', error);
            // Use default layout
            applyLayout(getDefaultLayout());
        }
    }
    
    // Serialize the current layout
    function serializeLayout() {
        const blocks = [];
        const blockElements = canvas.querySelectorAll('.block');
        
        blockElements.forEach(block => {
            const rect = block.getBoundingClientRect();
            const canvasRect = canvas.getBoundingClientRect();
            
            blocks.push({
                id: block.id,
                type: block.classList.contains('text') ? 'text' : 'image',
                content: block.innerHTML,
                position: {
                    left: rect.left - canvasRect.left,
                    top: rect.top - canvasRect.top,
                    width: rect.width,
                    height: rect.height
                }
            });
        });
        
        return {
            blocks: blocks,
            columns: 3,
            baseline: 24,
            gutter: 32,
            snap: true,
            zoom: 1.0,
            orientation: 'portrait',
            format: 'A4',
            dimensions: { width: 794, height: 1123 },
            layers: [
                {
                    id: 'layer-main',
                    name: 'Layer 1',
                    order: 0,
                }
            ],
            activeLayer: 'layer-main'
        };
    }
    
    // Apply layout to canvas
    function applyLayout(layout) {
        // Clear existing blocks
        canvas.innerHTML = '';
        
        // Add blocks from layout
        if (layout.blocks) {
            layout.blocks.forEach(blockData => {
                const block = document.createElement('div');
                block.className = `block ${blockData.type}`;
                block.id = blockData.id;
                block.innerHTML = blockData.content;
                
                block.style.left = blockData.position.left + 'px';
                block.style.top = blockData.position.top + 'px';
                block.style.width = blockData.position.width + 'px';
                block.style.height = blockData.position.height + 'px';
                
                // Add resize handle for text blocks
                if (blockData.type === 'text') {
                    const resizeHandle = document.createElement('div');
                    resizeHandle.className = 'resize-handle';
                    block.appendChild(resizeHandle);
                }
                
                canvas.appendChild(block);
                
                // Add event listeners to the block
                block.addEventListener('click', (e) => {
                    e.stopPropagation();
                    selectBlock(block);
                });
                
                // Add resize functionality
                if (blockData.type === 'text') {
                    const resizeHandle = block.querySelector('.resize-handle');
                    resizeHandle.addEventListener('mousedown', (e) => {
                        e.stopPropagation();
                        startResizing(e, block);
                    });
                }
            });
        }
    }
    
    // Get default layout
    function getDefaultLayout() {
        return {
            columns: 3,
            baseline: 24,
            gutter: 32,
            snap: true,
            zoom: 1.0,
            orientation: 'portrait',
            format: 'A4',
            dimensions: { width: 794, height: 1123 },
            blocks: [],
            layers: [
                {
                    id: 'layer-main',
                    name: 'Layer 1',
                    order: 0,
                }
            ],
            activeLayer: 'layer-main'
        };
    }
    
    // Initialize the application
    initApp();
});