// Pages management for Fyona Canvas Editor

class PagesManager {
    constructor() {
        this.pages = [];
        this.currentPageId = null;
        this.canvas = document.getElementById('canvas');
        this.pagesList = document.getElementById('pages-list');
        this.addPageBtn = document.getElementById('add-page');
        this.togglePagesSidebarBtn = document.getElementById('toggle-pages-sidebar');
        this.pagesSidebar = document.querySelector('.pages-sidebar');
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.loadPages();
    }
    
    setupEventListeners() {
        if (this.addPageBtn) {
            this.addPageBtn.addEventListener('click', () => this.addPage());
        }
        
        if (this.togglePagesSidebarBtn) {
            this.togglePagesSidebarBtn.addEventListener('click', () => this.togglePagesSidebar());
        }
    }
    
    // Toggle pages sidebar
    togglePagesSidebar() {
        if (!this.pagesSidebar) return;
        
        this.pagesSidebar.classList.toggle('collapsed');
        const icon = this.togglePagesSidebarBtn.querySelector('i');
        if (this.pagesSidebar.classList.contains('collapsed')) {
            icon.classList.remove('fa-chevron-left');
            icon.classList.add('fa-chevron-right');
        } else {
            icon.classList.remove('fa-chevron-right');
            icon.classList.add('fa-chevron-left');
        }
    }
    
    // Load pages from backend
    async loadPages() {
        try {
            const response = await fetch('/api/pages');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            this.pages = data.pages || [];
            this.renderPagesList();
        } catch (error) {
            console.error('Error loading pages:', error);
            this.pages = [];
            this.renderPagesList();
        }
    }
    
    // Render pages list in sidebar
    renderPagesList() {
        if (!this.pagesList) return;
        
        this.pagesList.innerHTML = '';
        
        // Sort pages by order
        const sortedPages = [...this.pages].sort((a, b) => (a.order || 0) - (b.order || 0));
        
        sortedPages.forEach(page => {
            const li = document.createElement('li');
            li.className = 'pages-list-item';
            if (page.id === this.currentPageId) {
                li.classList.add('active');
            }
            
            // Create preview element
            const preview = document.createElement('div');
            preview.className = 'page-preview';
            
            // Add visual representation of blocks
            if (page.blocks && page.blocks.length > 0) {
                this.renderPagePreview(preview, page.blocks);
            }
            
            const info = document.createElement('div');
            info.className = 'page-info';
            info.innerHTML = `
                <div class="page-title">${page.title || 'Untitled Page'}</div>
                <div class="page-stats">${(page.blocks || []).length} blocks</div>
            `;
            
            // Create delete button
            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'btn btn-icon btn-danger page-delete-btn';
            deleteBtn.innerHTML = '<i class="fas fa-times"></i>';
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.deletePage(page.id);
            });
            
            li.appendChild(preview);
            li.appendChild(info);
            li.appendChild(deleteBtn);
            
            li.addEventListener('click', () => this.switchToPage(page.id));
            this.pagesList.appendChild(li);
        });
    }
    
    // Render visual preview of page blocks
    renderPagePreview(previewElement, blocks) {
        // Clear any existing content
        previewElement.innerHTML = '';
        
        // Create a simple visual representation of blocks
        blocks.forEach(block => {
            const blockPreview = document.createElement('div');
            blockPreview.className = 'page-block-preview';
            
            // Position and size the block preview proportionally
            const position = block.position || {};
            const left = (position.left || 0) / 10; // Scale down for preview
            const top = (position.top || 0) / 10;
            const width = Math.max(5, (position.width || 50) / 10); // Minimum size
            const height = Math.max(3, (position.height || 30) / 10);
            
            blockPreview.style.left = `${left}px`;
            blockPreview.style.top = `${top}px`;
            blockPreview.style.width = `${width}px`;
            blockPreview.style.height = `${height}px`;
            
            // Style based on block type
            if (block.type === 'text') {
                blockPreview.style.backgroundColor = '#e0e0e0';
            } else if (block.type === 'image') {
                blockPreview.style.backgroundColor = '#bbdefb';
            } else {
                blockPreview.style.backgroundColor = '#f5f5f5';
            }
            
            previewElement.appendChild(blockPreview);
        });
    }
    
    // Switch to a specific page
    switchToPage(pageId) {
        const page = this.pages.find(p => p.id === pageId);
        if (!page) return;
        
        this.currentPageId = pageId;
        this.renderPagesList();
        
        // Clear current canvas
        if (this.canvas) {
            this.canvas.innerHTML = '<div class="canvas-grid"></div>';
            
            // Render blocks for this page
            if (page.blocks) {
                page.blocks.forEach(blockData => {
                    // We would need to call the block rendering function from the main app
                    // For now, we'll just log that we would render the blocks
                    console.log('Would render block:', blockData);
                });
            }
        }
    }
    
    // Add a new page
    async addPage() {
        try {
            const response = await fetch('/api/pages', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({})
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            this.pages.push(data.page);
            this.renderPagesList();
            
            // Switch to the new page
            this.switchToPage(data.page.id);
        } catch (error) {
            console.error('Error adding page:', error);
        }
    }
    
    // Delete a page
    async deletePage(pageId) {
        if (!confirm('Are you sure you want to delete this page? This cannot be undone.')) {
            return;
        }
        
        try {
            const response = await fetch(`/api/pages/${pageId}`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({})
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            // Remove page from local state
            this.pages = this.pages.filter(page => page.id !== pageId);
            
            // If we deleted the current page, switch to the first page
            if (this.currentPageId === pageId) {
                if (this.pages.length > 0) {
                    this.switchToPage(this.pages[0].id);
                } else {
                    this.currentPageId = null;
                    if (this.canvas) {
                        this.canvas.innerHTML = '<div class="canvas-grid"></div>';
                    }
                }
            }
            
            this.renderPagesList();
        } catch (error) {
            console.error('Error deleting page:', error);
            alert('Failed to delete page. Please try again.');
        }
    }
}

// Initialize pages manager when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.pagesManager = new PagesManager();
});

export default PagesManager;