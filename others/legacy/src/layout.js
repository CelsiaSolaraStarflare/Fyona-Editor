// Layout and serialization
function serializeLayout() {
    return Array.from(utils.$$('#block-layer .block')).map(block => ({
        id: block.dataset.id,
        type: block.dataset.type,
        x: parseInt(block.style.left),
        y: parseInt(block.style.top),
        w: parseInt(block.style.width),
        h: parseInt(block.style.height),
        content: block.querySelector('.block-inner').innerHTML,
        z: block.style.zIndex
    }));
}

async function saveLayout() {
    try {
        await fetch('/save-layout', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({layout: serializeLayout(), project: window.state.project})
        });
        utils.C('Layout saved');
    } catch (e) {
        utils.C('Save failed');
    }
}

async function loadLayout(project = 'default') {
    try {
        const response = await fetch(`/layout?project=${project}`);
        const layout = await response.json();
        
        // Clear existing blocks
        utils.$('#block-layer').innerHTML = '';
        
        // Create blocks from layout
        if (layout.blocks) {
            layout.blocks.forEach(b => {
                window.blocks.createBlock(b.type, {
                    x: b.x, y: b.y, w: b.w, h: b.h,
                    content: b.content, z: b.z
                });
            });
        }
        
        utils.C('Layout loaded');
    } catch (e) {
        utils.C('Load failed');
    }
}

function scheduleSave(label) {
    clearTimeout(window.saveTimer);
    window.saveTimer = setTimeout(() => saveLayout(), 500);
}

function clearCanvas() {
    utils.$('#block-layer').innerHTML = '';
    window.state.selectBlock(null);
    utils.C('Canvas cleared');
    scheduleSave('clear');
}

// Export functions
window.layout = { serializeLayout, saveLayout, loadLayout, scheduleSave, clearCanvas };