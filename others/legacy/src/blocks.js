// Block management
function createBlock(type, options = {}) {
    const block = utils.E('div', {className: `block ${type}-block`, dataset: {type, id: utils.genId()}});
    block.innerHTML = `<div class="block-controls">
        <button class="handle move"></button>
        <button class="handle resize"></button>
    </div><div class="block-inner" contenteditable="false">${options.content || utils.sampleContent(type)}</div>`;
    
    Object.assign(block.style, {
        left: (options.x || 100) + 'px',
        top: (options.y || 100) + 'px',
        width: (options.w || 200) + 'px',
        height: (options.h || 150) + 'px',
        background: options.bg || '#fff',
        zIndex: options.z || 1
    });
    
    block.onclick = () => window.state.selectBlock(block);
    block.querySelector('.block-inner').onclick = e => {
        e.stopPropagation();
        window.state.selectBlock(block);
        startEdit(block);
    };
    
    utils.$('#block-layer').appendChild(block);
    window.state.selectBlock(block);
    window.scheduleSave('create');
    utils.C(`${type} block created`);
    return block;
}

function selectBlock(block) {
    window.state.selectedBlock?.classList.remove('selected');
    window.state.selectedBlock = block;
    window.state.selectedBlock?.classList.add('selected');
    updateInspector();
}

function deleteBlock(block) {
    block?.remove();
    window.state.selectBlock(null);
    window.scheduleSave('delete');
    utils.C('Block deleted');
}

function duplicateBlock(block) {
    if (!block) return;
    const rect = block.getBoundingClientRect();
    createBlock(block.dataset.type, {
        x: rect.left + 20, y: rect.top + 20, 
        w: rect.width, h: rect.height,
        content: block.querySelector('.block-inner').innerHTML,
        bg: getComputedStyle(block).background,
        z: block.style.zIndex
    });
    utils.C('Block duplicated');
}

function adjustZ(direction) {
    if (!window.state.selectedBlock) return;
    const z = parseInt(window.state.selectedBlock.style.zIndex) || 1;
    window.state.selectedBlock.style.zIndex = direction === 'up' ? z + 1 : Math.max(1, z - 1);
    utils.C(`Z-index ${direction === 'up' ? 'increased' : 'decreased'}`);
    window.scheduleSave('zindex');
}

function startEdit(block) {
    const inner = block.querySelector('.block-inner');
    inner.contentEditable = true;
    inner.focus();
    window.state.activeEdit = inner;
    inner.onblur = () => { inner.contentEditable = false; window.state.activeEdit = null; window.scheduleSave('edit'); };
    inner.oninput = () => window.scheduleSave('typing');
}

function updateInspector() {
    if (!window.state.selectedBlock) return;
    const r = window.state.selectedBlock.getBoundingClientRect();
    utils.$('#inspector-x')?.value = Math.round(r.left);
    utils.$('#inspector-y')?.value = Math.round(r.top);
    utils.$('#inspector-width')?.value = r.width;
    utils.$('#inspector-height')?.value = r.height;
}

// Export functions
window.blocks = { createBlock, selectBlock, deleteBlock, duplicateBlock, adjustZ, startEdit, updateInspector };