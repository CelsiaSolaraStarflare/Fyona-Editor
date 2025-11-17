// Export functionality
async function exportPDF(useSnapshot = false) {
    const modal = utils.$('.export-modal');
    if (modal) modal.remove();
    
    utils.C(useSnapshot ? 'Exporting high-quality PDF...' : 'Exporting PDF...');
    
    try {
        const response = await fetch('/export/pdf', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                layout: window.layout.serializeLayout(),
                useSnapshotMethod: useSnapshot,
                dpi: useSnapshot ? 150 : 72 // Use lower DPI for better performance
            })
        });
        
        if (response.ok) {
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = utils.E('a', {href: url, download: `fiona-layout-${Date.now()}.pdf`});
            a.click();
            URL.revokeObjectURL(url);
            utils.C(useSnapshot ? 'High-quality PDF exported!' : 'PDF exported!');
        } else {
            const error = await response.json();
            utils.C(`Export failed: ${error.error || 'Server error'}`);
        }
    } catch (e) {
        utils.C('Export failed');
        console.error('Export error:', e);
    }
}

function showExportOptions() {
    const modal = utils.E('div', {className: 'modal export-modal'}, `
        <div class="export-options">
            <h3>PDF Export Options</h3>
            <button onclick="window.export.pdf(false)">Vector (Fast)</button>
            <button onclick="window.export.pdf(true)">Snapshot (Quality)</button>
            <button onclick="this.parentElement.parentElement.remove()">Cancel</button>
        </div>
    `);
    document.body.appendChild(modal);
}

// Export functions
window.export = { pdf: exportPDF, showOptions: showExportOptions };