document.addEventListener('DOMContentLoaded', () => {
    const els = {
        projectSelect: document.getElementById('project-select'),
        refreshProjects: document.getElementById('refresh-projects'),
        addText: document.getElementById('add-text'),
        addImage: document.getElementById('add-image'),
        saveLayout: document.getElementById('save-layout'),
        exportButton: document.getElementById('export-document'),
        exportFormat: document.getElementById('export-format'),
        canvas: document.getElementById('canvas'),
        canvasWrapper: document.querySelector('.canvas-wrapper'),
        canvasPanel: document.querySelector('.canvas-panel'),
        pagesPanel: document.querySelector('.pages-panel'),
        pagesList: document.getElementById('pages-list'),
        pagesEmpty: document.getElementById('pages-empty'),
        inspectorEmpty: document.getElementById('inspector-empty'),
        inspectorForm: document.getElementById('inspector-form'),
        inspectorType: document.getElementById('inspector-type'),
        inspectorContent: document.getElementById('inspector-content'),
        textOptions: document.getElementById('text-style-options'),
        inspectorFont: document.getElementById('inspector-font'),
        inspectorLeft: document.getElementById('inspector-left'),
        inspectorTop: document.getElementById('inspector-top'),
        inspectorWidth: document.getElementById('inspector-width'),
        inspectorHeight: document.getElementById('inspector-height'),
        inspectorBg: document.getElementById('inspector-bg'),
        inspectorFg: document.getElementById('inspector-fg'),
        inspectorRadius: document.getElementById('inspector-radius'),
        deleteBlock: document.getElementById('delete-block'),
        toastTemplate: document.getElementById('toast-template'),
        canvasFormat: document.getElementById('canvas-format'),
        toggleOrientation: document.getElementById('toggle-orientation'),
        canvasSizeLabel: document.getElementById('canvas-size-label'),
        imageUploadInput: document.getElementById('image-upload'),
        uploadImage: document.getElementById('upload-image'),
        imageOptions: document.getElementById('image-options'),
        zoomIn: document.getElementById('zoom-in'),
        zoomOut: document.getElementById('zoom-out'),
        canvasZoom: document.getElementById('canvas-zoom'),
        zoomLabel: document.getElementById('zoom-label'),
        chatLauncher: document.getElementById('chat-launcher'),
        chatPanel: document.getElementById('chat-panel'),
        chatClose: document.getElementById('chat-close'),
        chatLog: document.getElementById('chat-log'),
        chatForm: document.getElementById('chat-form'),
        chatInput: document.getElementById('chat-input'),
        chatAttachCanvas: document.getElementById('chat-attach-canvas'),
        chatAttachments: document.getElementById('chat-attachments'),
        chatStatus: document.getElementById('chat-status'),
        chatAgentToggle: document.getElementById('chat-agent-toggle'),
        chatAgentIndicator: document.getElementById('chat-agent-indicator'),
        chatResizeHandle: document.getElementById('chat-resize-handle'),
    };

    const params = new URLSearchParams(window.location.search);
    const initialProject = (params.get('project') || '').trim() || 'default';

    const state = {
        project: initialProject,
        layout: null,
        pages: [],
        activePageId: null,
        blocks: new Map(),
        blockOrder: [],
        blockElements: new Map(),
        selectedId: null,
        activePointer: null,
        format: 'A4',
        orientation: 'portrait',
        pendingImageBlock: null,
        zoom: 1,
        chat: {
            open: false,
            messages: [],
            pendingAttachments: [],
            sending: false,
            agentEnabled: false,
            agentSnapshot: null,
            panelSize: null,
            resizing: false,
        },
        terminal: {
            element: null,
            log: null,
            input: null,
            dragging: false,
            dragOffsetX: 0,
            dragOffsetY: 0,
            isOpen: false,
        },
    };

    const FONT_OPTIONS = [
        { value: 'inter', label: 'Inter', css: '"Inter", "Helvetica Neue", Arial, sans-serif' },
        { value: 'space-grotesk', label: 'Space Grotesk', css: '"Space Grotesk", "Inter", "Helvetica Neue", sans-serif' },
        { value: 'playfair', label: 'Playfair Display', css: '"Playfair Display", "Times New Roman", serif' },
        { value: 'merriweather', label: 'Merriweather', css: '"Merriweather", Georgia, serif' },
    ];

    const DEFAULT_FONT_VALUE = FONT_OPTIONS[0].value;

    const CANVAS_PRESETS = {
        A5: { width: 559, height: 794 },
        A4: { width: 794, height: 1123 },
        A3: { width: 1123, height: 1587 },
        Letter: { width: 816, height: 1056 },
    };

    const ZOOM_CONFIG = {
        min: 0.5,
        max: 5,
        step: 0.1,
    };

    let pendingFitFrame = null;
    let chatAttachmentId = 0;
    const CHAT_ATTACHMENT_LIMIT = 6;
    const CHAT_LAYOUT_PREVIEW_LIMIT = 6000;
    const CHAT_TREE_PREVIEW_LIMIT = 4000;
    const PAGE_THUMB_BLOCK_LIMIT = 4;
    const LAYOUT_SYNC_DELAY = 600;
    const CHAT_PANEL_MIN_WIDTH = 260;
    const CHAT_PANEL_MAX_WIDTH = 640;
    const CHAT_PANEL_MIN_HEIGHT = 260;
    const CHAT_PANEL_MAX_HEIGHT = 640;
    let layoutSyncTimeout = null;
    const AUTO_PAGE_NAME_PATTERN = /^page\s+\d+$/i;
    const hydratedPages = new Set();
    const chatResizeSession = {
        active: false,
        pointerId: null,
        startX: 0,
        startY: 0,
        startWidth: 0,
        startHeight: 0,
    };

    init();

    async function init() {
        configureZoomControl();
        initFontOptions();
        bindUIEvents();
        initChatInterface();
        window.addEventListener('resize', () => {
            scheduleCanvasFit();
            constrainTerminalToViewport();
            handleChatPanelBounds();
        });
        setCanvasZoom(state.zoom);
        await loadProjects();
        await loadLayout(state.project);
    }

    function configureZoomControl() {
        if (!els.canvasZoom) return;
        els.canvasZoom.min = ZOOM_CONFIG.min;
        els.canvasZoom.max = ZOOM_CONFIG.max;
        els.canvasZoom.step = ZOOM_CONFIG.step;
        els.canvasZoom.value = state.zoom;
    }

    function initFontOptions() {
        if (!els.inspectorFont) return;
        els.inspectorFont.innerHTML = '';
        FONT_OPTIONS.forEach((option) => {
            const opt = document.createElement('option');
            opt.value = option.value;
            opt.textContent = option.label;
            els.inspectorFont.appendChild(opt);
        });
        els.inspectorFont.value = DEFAULT_FONT_VALUE;
    }

    function bindUIEvents() {
        els.projectSelect.addEventListener('change', async (e) => {
            const project = e.target.value;
            await loadLayout(project);
            showToast(`Loaded project “${project}”`);
        });

        els.refreshProjects.addEventListener('click', () => {
            loadProjects(true);
        });

        els.addText.addEventListener('click', () => {
            createBlock('text');
        });

        els.addImage.addEventListener('click', () => {
            createBlock('image');
        });

        els.saveLayout.addEventListener('click', () => {
            saveCurrentLayout();
        });

        if (els.exportButton) {
            els.exportButton.addEventListener('click', () => {
                exportCurrentLayout();
            });
        }

        els.canvas.addEventListener('pointerdown', (e) => {
            if (e.target === els.canvas) {
                deselectBlock();
            }
        });

        els.inspectorContent.addEventListener('input', () => {
            const block = getSelectedBlock();
            if (!block) return;
            if (block.type === 'image') return;
            block.content = els.inspectorContent.value;
            applyBlockContent(block);
        });
        els.inspectorContent.addEventListener('blur', () => {
            const block = getSelectedBlock();
            if (!block) return;
            if (block.type === 'image') return;
            persistBlock(block.id, { content: block.content });
        });

        if (els.inspectorFont) {
            els.inspectorFont.addEventListener('change', () => {
                const block = getSelectedBlock();
                if (!block || block.type === 'image') return;
                const fontValue = sanitizeFontValue(els.inspectorFont.value);
                block.typography = { ...(block.typography || {}), fontFamily: fontValue };
                applyBlockTypography(block);
                persistBlock(block.id, { typography: { ...block.typography } });
            });
        }

        bindNumericInput(els.inspectorLeft, 'left');
        bindNumericInput(els.inspectorTop, 'top');
        bindNumericInput(els.inspectorWidth, 'width', 40);
        bindNumericInput(els.inspectorHeight, 'height', 40);

        els.inspectorBg.addEventListener('input', () => {
            const block = getSelectedBlock();
            if (!block) return;
            block.backgroundColor = els.inspectorBg.value;
            applyBlockAppearance(block);
        });
        els.inspectorBg.addEventListener('change', () => {
            const block = getSelectedBlock();
            if (!block) return;
            persistBlock(block.id, { backgroundColor: block.backgroundColor });
        });

        els.inspectorFg.addEventListener('input', () => {
            const block = getSelectedBlock();
            if (!block) return;
            block.textColor = els.inspectorFg.value;
            applyBlockAppearance(block);
        });
        els.inspectorFg.addEventListener('change', () => {
            const block = getSelectedBlock();
            if (!block) return;
            persistBlock(block.id, { textColor: block.textColor });
        });

        els.inspectorRadius.addEventListener('input', () => {
            const block = getSelectedBlock();
            if (!block) return;
            const radius = clampNumber(parseInt(els.inspectorRadius.value, 10), 0, 120);
            block.borderRadius = radius;
            els.inspectorRadius.value = radius;
            applyBlockAppearance(block);
        });
        els.inspectorRadius.addEventListener('change', () => {
            const block = getSelectedBlock();
            if (!block) return;
            persistBlock(block.id, { borderRadius: block.borderRadius });
        });

        els.deleteBlock.addEventListener('click', () => {
            const block = getSelectedBlock();
            if (!block) return;
            deleteBlock(block.id);
        });

        els.canvasFormat.addEventListener('change', () => {
            const format = els.canvasFormat.value;
            setCanvasFormat(format, state.orientation);
        });

        els.toggleOrientation.addEventListener('click', () => {
            const nextOrientation = state.orientation === 'portrait' ? 'landscape' : 'portrait';
            setCanvasFormat(state.format, nextOrientation);
        });

        if (els.imageUploadInput) {
            els.imageUploadInput.addEventListener('change', handleImageUploadSelection);
        }

        if (els.uploadImage) {
            els.uploadImage.addEventListener('click', () => {
                const block = getSelectedBlock();
                if (!block || block.type !== 'image') return;
                triggerImageUpload(block.id);
            });
        }

        if (els.canvasZoom) {
            els.canvasZoom.addEventListener('input', (event) => {
                const value = Number(event.target.value);
                setCanvasZoom(value);
            });
        }

        if (els.zoomIn) {
            els.zoomIn.addEventListener('click', () => adjustCanvasZoom(ZOOM_CONFIG.step));
        }

        if (els.zoomOut) {
            els.zoomOut.addEventListener('click', () => adjustCanvasZoom(-ZOOM_CONFIG.step));
        }

        const zoomWheelTarget = els.canvasWrapper || els.canvas;
        if (zoomWheelTarget) {
            zoomWheelTarget.addEventListener('wheel', handleZoomWheel, { passive: false });
        }

    }


    function bindNumericInput(input, field, min = null) {
        input.addEventListener('change', () => {
            const block = getSelectedBlock();
            if (!block) return;
            let value = Number(input.value);
            if (!Number.isFinite(value)) value = 0;
            if (min !== null && value < min) value = min;
            block.position[field] = Math.round(value);
            input.value = block.position[field];
            applyBlockPosition(block);
            persistBlock(block.id, { position: { ...block.position } });
        });
    }

    async function loadProjects(showToastMessage = false) {
        try {
            const response = await fetch('/api/projects');
            if (!response.ok) throw new Error('Failed to fetch projects');
            const data = await response.json();
            populateProjects(data.projects);
            if (showToastMessage) {
                showToast('Project list refreshed');
            }
        } catch (error) {
            console.error(error);
            showToast('Unable to load projects', true);
        }
    }

    function populateProjects(projects) {
        if (!els.projectSelect) return;
        const current = state.project;
        els.projectSelect.innerHTML = '';
        projects.forEach((project) => {
            const option = document.createElement('option');
            option.value = project;
            option.textContent = project;
            if (project === current) {
                option.selected = true;
            }
            els.projectSelect.appendChild(option);
        });
    }

    async function loadLayout(project) {
        const previousProject = state.project;
        try {
            const response = await fetch(`/api/layout?project=${encodeURIComponent(project)}`);
            if (!response.ok) throw new Error('Failed to fetch layout');
            const layout = await response.json();

            state.project = layout.project || project;
            if (els.projectSelect) {
                const hasOption = Array.from(els.projectSelect.options).some((opt) => opt.value === state.project);
                if (!hasOption) {
                    const option = document.createElement('option');
                    option.value = state.project;
                    option.textContent = state.project;
                    els.projectSelect.appendChild(option);
                }
                els.projectSelect.value = state.project;
            }
            if (previousProject !== project && state.chat.agentEnabled) {
                state.chat.agentEnabled = false;
                state.chat.agentSnapshot = null;
                updateAgentToggle();
            }
            state.layout = { ...layout };
            state.pages = normalizePagesFromLayout(layout);
            hydratedPages.clear();
            state.layout.pages = state.pages;
            const requestedActive = layout.activePageId || state.activePageId;
            const hasRequested = state.pages.some((page) => page.id === requestedActive);
            state.activePageId = hasRequested ? requestedActive : state.pages[0]?.id || null;

            applyCanvasMeta(state.layout);
            const activePage = getActivePage();
            state.layout.pages = state.pages;
            state.layout.activePageId = state.activePageId;
            state.layout.blocks = activePage ? activePage.blocks : [];

            if (activePage) {
                setActivePage(activePage.id, { silent: true, skipPersist: true, force: true });
            } else {
                state.blocks.clear();
                state.blockElements.forEach((el) => el.remove());
                state.blockElements.clear();
                state.blockOrder = [];
                els.canvas.innerHTML = '';
                renderPagesSidebar();
            }
            deselectBlock();
            updateCanvasSizeLabel();
            updateChatProjectStatus();
        } catch (error) {
            console.error(error);
            showToast('Unable to load layout', true);
        }
    }

    function generateClientId() {
        return `block-${Math.random().toString(16).slice(2, 10)}`;
    }

    function generatePageId() {
        return `page-${Math.random().toString(16).slice(2, 10)}`;
    }

    function normalizeBlock(block) {
        const position = block.position || {};
        const id = block.id || generateClientId();
        const typography = (block.typography && typeof block.typography === 'object')
            ? { ...block.typography }
            : {};
        typography.fontFamily = sanitizeFontValue(typography.fontFamily);
        return {
            id,
            type: block.type || 'text',
            content: block.content ?? '',
            backgroundColor: block.backgroundColor ?? '#ffffff',
            textColor: block.textColor ?? '#1c2333',
            borderRadius: typeof block.borderRadius === 'number' ? block.borderRadius : 12,
            imageUrl: block.imageUrl || null,
            typography,
            position: {
                left: Math.round(Number(position.left) || 0),
                top: Math.round(Number(position.top) || 0),
                width: Math.max(40, Math.round(Number(position.width) || 240)),
                height: Math.max(40, Math.round(Number(position.height) || 140)),
            },
        };
    }

    function normalizePagesFromLayout(layout) {
        const rawPages = Array.isArray(layout?.pages) ? layout.pages : [];
        const pagesSource = rawPages.length ? rawPages : [
            {
                id: layout?.activePageId,
                name: 'Page 1',
                order: 0,
                blocks: layout?.blocks || [],
                dimensions: layout?.dimensions,
            },
        ];
        const normalized = pagesSource
            .filter((page) => page && typeof page === 'object')
            .map((page, index) => {
                const pageId = typeof page.id === 'string' && page.id.trim() ? page.id : generatePageId();
                const nameValue = page.name || page.title || `Page ${index + 1}`;
                const name = String(nameValue).trim() || `Page ${index + 1}`;
                const orderValue = typeof page.order === 'number' ? page.order : index;
                const blocks = Array.isArray(page.blocks) ? page.blocks.map((block) => normalizeBlock(block)) : [];
                const payload = {
                    id: pageId,
                    name,
                    order: orderValue,
                    blocks,
                };
                if (page.dimensions && typeof page.dimensions === 'object') {
                    payload.dimensions = { ...page.dimensions };
                }
                return payload;
            })
            .sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
        normalized.forEach((page, index) => {
            page.order = index;
        });
        return normalized;
    }

    function getActivePage() {
        if (!state.pages.length) return null;
        return state.pages.find((page) => page.id === state.activePageId) || state.pages[0];
    }

    function setActivePage(pageId, options = {}) {
        if (state.activePageId && hydratedPages.has(state.activePageId)) {
            syncActivePageBlocks();
        }
        const target = state.pages.find((page) => page.id === pageId) || state.pages[0] || null;
        if (!target) {
            state.activePageId = null;
            state.layout.activePageId = null;
            state.blocks.clear();
            state.blockOrder = [];
            state.blockElements.forEach((el) => el.remove());
            state.blockElements.clear();
            if (els.canvas) {
                els.canvas.innerHTML = '';
            }
            renderPagesSidebar();
            return;
        }
        const force = options.force;
        if (state.activePageId === target.id && !force) {
            renderPagesSidebar();
            return;
        }

        deselectBlock();
        state.activePageId = target.id;
        state.layout.activePageId = target.id;
        state.layout.blocks = target.blocks;
        state.blocks.clear();
        state.blockOrder = [];
        state.blockElements.forEach((el) => el.remove());
        state.blockElements.clear();
        target.blocks.forEach((block) => {
            state.blocks.set(block.id, block);
            state.blockOrder.push(block.id);
        });
        renderCanvas();
        renderPagesSidebar();
        hydratedPages.add(target.id);
        if (!options.silent) {
            showToast(`Editing ${target.name}`);
        }
        if (!options.skipPersist) {
            queueLayoutSync();
        }
    }

    function resortPages() {
        state.pages.sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
        state.pages.forEach((page, index) => {
            page.order = index;
            const expectedName = `Page ${index + 1}`;
            if (!page.name || AUTO_PAGE_NAME_PATTERN.test(page.name)) {
                page.name = expectedName;
            }
        });
    }

    function renderPagesSidebar() {
        if (!els.pagesList) return;
        const container = els.pagesList;
        container.innerHTML = '';
        resortPages();
        if (!state.pages.length) {
            if (els.pagesEmpty) {
                els.pagesEmpty.hidden = false;
            }
            const button = createPageInsertButton(0);
            button.classList.add('page-insert--standalone');
            container.appendChild(button);
            return;
        }
        if (els.pagesEmpty) {
            els.pagesEmpty.hidden = true;
        }
        container.appendChild(createPageInsertButton(0));
        state.pages.forEach((page, index) => {
            container.appendChild(createPagePreview(page));
            container.appendChild(createPageInsertButton(index + 1));
        });
    }

    function createPageInsertButton(index) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'page-insert';
        button.dataset.index = index;
        button.textContent = 'Add page';
        button.setAttribute('aria-label', `Add page at position ${index + 1}`);
        button.addEventListener('click', () => {
            createPageAtIndex(Number(index));
        });
        return button;
    }

    function createPagePreview(page) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'page-thumb';
        if (page.id === state.activePageId) {
            button.classList.add('page-thumb--active');
        }
        button.dataset.pageId = page.id;
        if (page.id === state.activePageId) {
            button.setAttribute('aria-current', 'page');
        } else {
            button.removeAttribute('aria-current');
        }

        const preview = document.createElement('div');
        preview.className = 'page-thumb__preview';
        const previewCanvas = document.createElement('div');
        previewCanvas.className = 'page-thumb__preview-canvas';
        const dims = state.layout?.dimensions || CANVAS_PRESETS[state.format] || CANVAS_PRESETS.A4;
        (page.blocks || []).slice(0, PAGE_THUMB_BLOCK_LIMIT).forEach((block) => {
            if (!block?.position) return;
            const mini = document.createElement('div');
            mini.className = 'page-thumb__mini-block';
            if (block.type === 'image') {
                mini.classList.add('page-thumb__mini-block--image');
            }
            const widthRatio = clampNumber(block.position.width / dims.width, 0.18, 1);
            const heightRatio = clampNumber(block.position.height / dims.height, 0.08, 0.45);
            const leftRatio = clampNumber(block.position.left / dims.width, 0, 1 - widthRatio);
            const topRatio = clampNumber(block.position.top / dims.height, 0, 1 - heightRatio);
            mini.style.width = `${Math.round(widthRatio * 100)}%`;
            mini.style.height = `${Math.round(heightRatio * 100)}%`;
            mini.style.left = `${Math.round(leftRatio * 100)}%`;
            mini.style.top = `${Math.round(topRatio * 100)}%`;
            previewCanvas.appendChild(mini);
        });
        preview.appendChild(previewCanvas);

        const meta = document.createElement('div');
        meta.className = 'page-thumb__meta';
        const label = document.createElement('span');
        label.className = 'page-thumb__label';
        label.textContent = page.name;
        const count = document.createElement('span');
        const blockCount = page.blocks?.length || 0;
        count.textContent = `${blockCount} block${blockCount === 1 ? '' : 's'}`;
        meta.appendChild(label);
        meta.appendChild(count);

        button.appendChild(preview);
        button.appendChild(meta);
        button.addEventListener('click', () => {
            setActivePage(page.id);
        });
        return button;
    }

    function createPageAtIndex(index) {
        const safeIndex = Math.max(0, Math.min(typeof index === 'number' ? index : 0, state.pages.length));
        const label = `Page ${safeIndex + 1}`;
        const newPage = {
            id: generatePageId(),
            name: label,
            order: safeIndex,
            blocks: [],
        };
        state.pages.splice(safeIndex, 0, newPage);
        resortPages();
        state.layout.pages = state.pages;
        setActivePage(newPage.id, { force: true });
    }

    function syncActivePageBlocks() {
        if (!state.activePageId || !hydratedPages.has(state.activePageId)) {
            return;
        }
        const page = getActivePage();
        if (!page) return;
        page.blocks = state.blockOrder
            .map((id) => state.blocks.get(id))
            .filter(Boolean);
        state.layout.blocks = page.blocks;
    }

    function getPageIdForBlock(blockId) {
        const { page } = findBlockInPages(blockId);
        return page?.id || state.activePageId;
    }

    function findBlockInPages(blockId) {
        for (const page of state.pages) {
            const block = page.blocks.find((item) => item.id === blockId);
            if (block) {
                return { page, block };
            }
        }
        return { page: null, block: null };
    }

    function renderCanvas() {
        els.canvas.innerHTML = '';
        state.blockElements.clear();

        state.blockOrder.forEach((id) => {
            const block = state.blocks.get(id);
            if (!block || !block.id) return;
            const element = createBlockElement(block);
            els.canvas.appendChild(element);
            state.blockElements.set(id, element);
        });
    }

    function createBlockElement(block) {
        const blockEl = document.createElement('div');
        blockEl.className = 'block';
        blockEl.dataset.id = block.id;
        if (block.type === 'image') {
            blockEl.classList.add('block--image');
        }

        const contentWrapper = document.createElement('div');
        contentWrapper.className = 'block__content-wrapper';
        blockEl.appendChild(contentWrapper);

        if (block.type === 'image' && block.imageUrl) {
            const img = document.createElement('img');
            img.className = 'block__media';
            img.src = block.imageUrl;
            img.alt = block.content || 'Image block';
            contentWrapper.appendChild(img);
        } else {
            const contentEl = document.createElement('div');
            contentEl.className = 'block__content';
            contentEl.textContent = block.content || (block.type === 'image' ? '[Double-click to add image]' : '');
            contentWrapper.appendChild(contentEl);
        }

        const resizeHandle = document.createElement('div');
        resizeHandle.className = 'resize-handle';
        blockEl.appendChild(resizeHandle);

        applyBlockPosition(block, blockEl);
        applyBlockAppearance(block, blockEl);

        blockEl.addEventListener('click', (event) => {
            event.stopPropagation();
            selectBlock(block.id);
        });

        blockEl.addEventListener('pointerdown', (event) => {
            if (event.pointerType === 'mouse' && event.button !== 0) return;
            if (event.detail > 1) return;
            const target = event.target;
            selectBlock(block.id);

            if (target.classList.contains('resize-handle')) {
                startPointerInteraction(event, block.id, 'resize');
            } else {
                startPointerInteraction(event, block.id, 'drag');
            }
        });

        blockEl.addEventListener('dblclick', (event) => {
            event.stopPropagation();
            if (block.type === 'image') {
                triggerImageUpload(block.id);
            }
        });

        return blockEl;
    }

    function startPointerInteraction(event, blockId, mode) {
        if (state.activePointer) return;
        const block = state.blocks.get(blockId);
        const element = state.blockElements.get(blockId);
        if (!block || !element) return;

        event.preventDefault();
        element.setPointerCapture(event.pointerId);

        state.activePointer = {
            blockId,
            pointerId: event.pointerId,
            mode,
            startX: event.clientX,
            startY: event.clientY,
            originLeft: block.position.left,
            originTop: block.position.top,
            originWidth: block.position.width,
            originHeight: block.position.height,
        };

        const moveHandler = (e) => handlePointerMove(e, element);
        const upHandler = (e) => endPointerInteraction(e, element, moveHandler, upHandler);

        element.addEventListener('pointermove', moveHandler);
        element.addEventListener('pointerup', upHandler);
        element.addEventListener('pointercancel', upHandler);
    }

    function handlePointerMove(event, element) {
        const active = state.activePointer;
        if (!active || event.pointerId !== active.pointerId) return;
        const block = state.blocks.get(active.blockId);
        if (!block) return;

        const dx = event.clientX - active.startX;
        const dy = event.clientY - active.startY;
        const scale = state.zoom || 1;

        if (active.mode === 'drag') {
            block.position.left = Math.round(active.originLeft + dx / scale);
            block.position.top = Math.round(active.originTop + dy / scale);
        } else if (active.mode === 'resize') {
            block.position.width = Math.max(40, Math.round(active.originWidth + dx / scale));
            block.position.height = Math.max(40, Math.round(active.originHeight + dy / scale));
        }

        applyBlockPosition(block);
        if (state.selectedId === block.id) {
            updateInspector(block);
        }
    }

    function endPointerInteraction(event, element, moveHandler, upHandler) {
        const active = state.activePointer;
        if (!active || event.pointerId !== active.pointerId) return;

        element.releasePointerCapture(event.pointerId);
        element.removeEventListener('pointermove', moveHandler);
        element.removeEventListener('pointerup', upHandler);
        element.removeEventListener('pointercancel', upHandler);

        const block = state.blocks.get(active.blockId);
        if (block) {
            persistBlock(block.id, { position: { ...block.position } });
        }

        state.activePointer = null;
    }

    async function createBlock(type) {
        const page = getActivePage();
        if (!page) {
            showToast('Add a page before placing blocks', true);
            return;
        }
        const basePosition = {
            left: 120 + Math.floor(Math.random() * 60),
            top: 120 + Math.floor(Math.random() * 60),
            width: type === 'image' ? 260 : 260,
            height: type === 'image' ? 180 : 140,
        };

        const payload = {
            project: state.project,
            operation: 'add',
            page_id: page.id,
            block: {
                type,
                content: type === 'image' ? 'Double-click to add image' : 'Editable text',
                position: basePosition,
                backgroundColor: '#ffffff',
                textColor: '#1c2333',
                borderRadius: 12,
                imageUrl: null,
                typography: { fontFamily: DEFAULT_FONT_VALUE },
            },
        };

        try {
            const response = await fetch('/api/block', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            if (!response.ok) throw new Error('Failed to create block');
            const data = await response.json();
            const block = normalizeBlock(data.block);
            state.blocks.set(block.id, block);
            state.blockOrder.push(block.id);
            page.blocks.push(block);
            state.layout.blocks = page.blocks;

            const element = createBlockElement(block);
            els.canvas.appendChild(element);
            state.blockElements.set(block.id, element);
            selectBlock(block.id);
            syncActivePageBlocks();
            renderPagesSidebar();
            showToast(`${type === 'image' ? 'Image' : 'Text'} block added`);
        } catch (error) {
            console.error(error);
            showToast('Unable to add block', true);
        }
    }

    async function deleteBlock(blockId) {
        const { page } = findBlockInPages(blockId);
        if (!page) {
            showToast('Block not found', true);
            return;
        }
        try {
            const response = await fetch('/api/block', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    project: state.project,
                    operation: 'delete',
                    block_id: blockId,
                    page_id: page.id,
                }),
            });
            if (!response.ok) throw new Error('Failed to delete block');

            const element = state.blockElements.get(blockId);
            if (element) element.remove();
            state.blockElements.delete(blockId);
            state.blocks.delete(blockId);
            state.blockOrder = state.blockOrder.filter((id) => id !== blockId);
            page.blocks = page.blocks.filter((block) => block.id !== blockId);
            syncActivePageBlocks();
            renderPagesSidebar();
            deselectBlock();
            showToast('Block deleted');
        } catch (error) {
            console.error(error);
            showToast('Unable to delete block', true);
        }
    }

    async function persistBlock(blockId, updates) {
        const pageId = getPageIdForBlock(blockId);
        try {
            await fetch('/api/block', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    project: state.project,
                    operation: 'update',
                    block_id: blockId,
                    page_id: pageId,
                    updates,
                }),
            });
        } catch (error) {
            console.error(error);
            showToast('Unable to sync block', true);
        }
    }

    function buildLayoutPayload() {
        syncActivePageBlocks();
        const pages = state.pages.map((page, index) => ({
            ...page,
            order: index,
            blocks: page.blocks.map((block) => ({
                ...block,
                position: { ...block.position },
                typography: block.typography ? { ...block.typography } : undefined,
            })),
        }));
        const activeBlocks = getActivePage()?.blocks || [];
        return {
            ...state.layout,
            project: state.project,
            pages,
            blocks: activeBlocks.map((block) => ({
                ...block,
                position: { ...block.position },
                typography: block.typography ? { ...block.typography } : undefined,
            })),
            activePageId: state.activePageId,
        };
    }

    function queueLayoutSync(delay = LAYOUT_SYNC_DELAY) {
        if (layoutSyncTimeout) {
            clearTimeout(layoutSyncTimeout);
        }
        layoutSyncTimeout = setTimeout(() => {
            layoutSyncTimeout = null;
            syncLayoutSilently();
        }, delay);
    }

    async function syncLayoutSilently() {
        if (!state.layout) return;
        const layout = buildLayoutPayload();
        try {
            await fetch('/api/layout', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    project: state.project,
                    layout,
                }),
            });
        } catch (error) {
            console.warn('Unable to sync layout structure', error);
        }
    }

    async function saveCurrentLayout() {
        const layout = buildLayoutPayload();

        try {
            const response = await fetch('/api/layout', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    project: state.project,
                    layout,
                }),
            });
            if (!response.ok) throw new Error('Save failed');
            showToast('Layout saved');
        } catch (error) {
            console.error(error);
            showToast('Unable to save layout', true);
        }
    }

    async function exportCurrentLayout() {
        if (!els.exportButton) return;
        const button = els.exportButton;
        if (button.disabled) return;
        const format = (els.exportFormat && els.exportFormat.value) || 'pdf';
        const defaultLabel = button.dataset.label || button.textContent || 'Download';
        button.dataset.label = defaultLabel;
        button.disabled = true;
        button.textContent = 'Preparing…';
        try {
            const encodedFormat = encodeURIComponent(format);
            const url = `/api/export/${encodedFormat}?project=${encodeURIComponent(state.project)}`;
            const response = await fetch(url);
            if (!response.ok) {
                let message = 'Unable to export document';
                try {
                    const data = await response.json();
                    if (data && data.error) {
                        message = data.error;
                    }
                } catch (_) {
                    // ignored – fallback to default message
                }
                throw new Error(message);
            }

            const blob = await response.blob();
            const digest = response.headers.get('x-layout-digest');
            const filename = response.headers.get('x-download-filename') || buildExportFilename(format);
            triggerFileDownload(blob, filename);
            const label = format.toUpperCase();
            const digestNote = digest ? ` • digest ${digest.slice(0, 8)}…` : '';
            showToast(`${label} exported${digestNote}`);
        } catch (error) {
            console.error(error);
            showToast(error.message || 'Unable to export document', true);
        } finally {
            button.disabled = false;
            button.textContent = button.dataset.label || 'Download';
        }
    }

    function selectBlock(blockId) {
        if (state.selectedId === blockId) return;
        if (state.selectedId) {
            const previousElement = state.blockElements.get(state.selectedId);
            if (previousElement) previousElement.classList.remove('selected');
        }

        const element = state.blockElements.get(blockId);
        const block = state.blocks.get(blockId);
        if (!element || !block) {
            state.selectedId = null;
            updateInspector(null);
            return;
        }

        element.classList.add('selected');
        state.selectedId = blockId;
        updateInspector(block);
    }

    function deselectBlock() {
        if (state.selectedId) {
            const element = state.blockElements.get(state.selectedId);
            if (element) element.classList.remove('selected');
        }
        state.selectedId = null;
        updateInspector(null);
    }

    function getSelectedBlock() {
        if (!state.selectedId) return null;
        return state.blocks.get(state.selectedId) || null;
    }

    function applyBlockPosition(block, element = state.blockElements.get(block.id)) {
        if (!element) return;
        const { left, top, width, height } = block.position;
        element.style.left = `${left}px`;
        element.style.top = `${top}px`;
        element.style.width = `${width}px`;
        element.style.height = `${height}px`;
    }

    function applyBlockAppearance(block, element = state.blockElements.get(block.id)) {
        if (!element) return;
        element.style.background = block.backgroundColor || '#ffffff';
        element.style.color = block.textColor || '#1c2333';
        element.style.borderRadius = `${block.borderRadius ?? 12}px`;
        applyBlockContent(block, element);
    }

    function applyBlockContent(block, element = state.blockElements.get(block.id)) {
        if (!element) return;
        const wrapper = element.querySelector('.block__content-wrapper');
        if (!wrapper) return;
        wrapper.innerHTML = '';

        if (block.type === 'image') {
            if (block.imageUrl) {
                const img = document.createElement('img');
                img.className = 'block__media';
                img.src = block.imageUrl;
                img.alt = block.content || 'Image block';
                wrapper.appendChild(img);
            } else {
                const placeholder = document.createElement('div');
                placeholder.className = 'block__content';
                placeholder.textContent = block.content || '[Double-click to add image]';
                wrapper.appendChild(placeholder);
            }
            return;
        }

        const contentEl = document.createElement('div');
        contentEl.className = 'block__content';
        contentEl.textContent = block.content ?? '';
        wrapper.appendChild(contentEl);
        applyBlockTypography(block, element);
    }

    function applyBlockTypography(block, element = state.blockElements.get(block.id)) {
        if (!element || block.type === 'image') return;
        const contentEl = element.querySelector('.block__content');
        if (!contentEl) return;
        const fontOption = getFontOption(block.typography?.fontFamily);
        contentEl.style.fontFamily = fontOption.css;
    }

    function updateInspector(block) {
        if (!block) {
            els.inspectorForm.hidden = true;
            els.inspectorEmpty.hidden = false;
            if (els.imageOptions) {
                els.imageOptions.hidden = true;
            }
            if (els.textOptions) {
                els.textOptions.hidden = true;
            }
            return;
        }

        els.inspectorEmpty.hidden = true;
        els.inspectorForm.hidden = false;

        const isImage = block.type === 'image';
        els.inspectorType.value = block.type;
        els.inspectorContent.value = block.content ?? '';
        els.inspectorContent.disabled = isImage;
        els.inspectorContent.placeholder = isImage ? 'Double-click image block to upload' : 'Edit block content';
        if (els.imageOptions) {
            els.imageOptions.hidden = !isImage;
        }
        if (els.textOptions) {
            els.textOptions.hidden = isImage;
        }
        if (els.inspectorFont) {
            const fontValue = sanitizeFontValue(block.typography?.fontFamily);
            block.typography = { ...(block.typography || {}), fontFamily: fontValue };
            els.inspectorFont.value = fontValue;
            els.inspectorFont.disabled = isImage;
        }
        els.inspectorLeft.value = block.position.left;
        els.inspectorTop.value = block.position.top;
        els.inspectorWidth.value = block.position.width;
        els.inspectorHeight.value = block.position.height;
        els.inspectorBg.value = toHexColor(block.backgroundColor ?? '#ffffff');
        els.inspectorFg.value = toHexColor(block.textColor ?? '#1c2333');
        els.inspectorRadius.value = block.borderRadius ?? 12;
    }

    function toHexColor(value) {
        if (!value) return '#ffffff';
        if (value.startsWith('#')) return value;
        const context = document.createElement('div');
        context.style.color = value;
        document.body.appendChild(context);
        const computed = getComputedStyle(context).color;
        document.body.removeChild(context);
        const match = computed.match(/^rgba?\((\d+),\s*(\d+),\s*(\d+)/);
        if (!match) return '#ffffff';
        const r = Number(match[1]).toString(16).padStart(2, '0');
        const g = Number(match[2]).toString(16).padStart(2, '0');
        const b = Number(match[3]).toString(16).padStart(2, '0');
        return `#${r}${g}${b}`;
    }

    function triggerFileDownload(blob, filename) {
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename || 'layout.pdf';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    }

    function buildExportFilename(format) {
        const base = state.project || 'layout';
        const normalized = (format || 'pdf').toLowerCase();
        const extensionMap = {
            pdf: 'pdf',
            png: 'png',
            jpeg: 'jpg',
            jpg: 'jpg',
            doc: 'docx',
            docx: 'docx',
            word: 'docx',
            ppt: 'pptx',
            pptx: 'pptx',
            powerpoint: 'pptx',
        };
        const extension = extensionMap[normalized] || normalized;
        return `${base}-layout.${extension}`;
    }

    function sanitizeFontValue(value) {
        if (typeof value === 'string') {
            const normalized = value.trim().toLowerCase();
            const match = FONT_OPTIONS.find((option) => option.value === normalized);
            if (match) {
                return match.value;
            }
        }
        return DEFAULT_FONT_VALUE;
    }

    function getFontOption(value) {
        if (typeof value === 'string') {
            const normalized = value.trim().toLowerCase();
            const match = FONT_OPTIONS.find((option) => option.value === normalized);
            if (match) {
                return match;
            }
        }
        return FONT_OPTIONS[0];
    }

    function showToast(message, isError = false) {
        if (!els.toastTemplate) return;
        const toast = els.toastTemplate.content.firstElementChild.cloneNode(true);
        const messageEl = toast.querySelector('.toast__message');
        messageEl.textContent = message;
        if (isError) {
            toast.style.background = 'rgba(229, 83, 83, 0.95)';
        }
        document.body.appendChild(toast);
        requestAnimationFrame(() => toast.classList.add('show'));
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 200);
        }, 2200);
    }

    function clampNumber(value, min, max) {
        return Math.min(max, Math.max(min, value));
    }

    function setCanvasZoom(value) {
        const zoom = clampNumber(Number.isFinite(value) ? value : state.zoom, ZOOM_CONFIG.min, ZOOM_CONFIG.max);
        state.zoom = Number(zoom.toFixed(2));
        document.documentElement.style.setProperty('--canvas-zoom', state.zoom);
        if (els.canvasZoom && Number(els.canvasZoom.value) !== state.zoom) {
            els.canvasZoom.value = state.zoom;
        }
        if (els.zoomLabel) {
            els.zoomLabel.textContent = `${Math.round(state.zoom * 100)}%`;
        }
        centerCanvasInViewport();
    }

    function scheduleCanvasFit() {
        if (!state.layout) return;
        if (pendingFitFrame) {
            cancelAnimationFrame(pendingFitFrame);
        }
        pendingFitFrame = requestAnimationFrame(() => {
            pendingFitFrame = null;
            fitCanvasToPanel();
        });
    }

    function fitCanvasToPanel() {
        const dims = state.layout?.dimensions;
        if (!dims || !dims.width || !dims.height) return;
        const container = els.canvasPanel || els.canvasWrapper;
        if (!container) return;
        const styles = window.getComputedStyle(container);
        const paddingX = (parseFloat(styles.paddingLeft) || 0) + (parseFloat(styles.paddingRight) || 0);
        const availableWidth = Math.max(container.clientWidth - paddingX, 120);
        if (!Number.isFinite(availableWidth) || availableWidth <= 0) return;
        const widthZoom = availableWidth / dims.width;
        const desiredZoom = widthZoom;
        if (!Number.isFinite(desiredZoom) || desiredZoom <= 0) return;
        const nextZoom = clampNumber(desiredZoom, ZOOM_CONFIG.min, ZOOM_CONFIG.max);
        if (Math.abs(nextZoom - state.zoom) < 0.01) {
            centerCanvasInViewport();
            return;
        }
        setCanvasZoom(nextZoom);
    }

    function adjustCanvasZoom(delta) {
        const raw = state.zoom + delta;
        const snapped = Math.round(raw / ZOOM_CONFIG.step) * ZOOM_CONFIG.step;
        setCanvasZoom(parseFloat(snapped.toFixed(2)));
    }

    function handleZoomWheel(event) {
        if (!event.metaKey && !event.ctrlKey) return;
        event.preventDefault();
        if (!event.deltaY) return;
        const direction = event.deltaY < 0 ? 1 : -1;
        adjustCanvasZoom(direction * ZOOM_CONFIG.step);
    }

    function applyCanvasMeta(layout) {
        const format = layout?.format && CANVAS_PRESETS[layout.format] ? layout.format : 'A4';
        const orientation = layout?.orientation === 'landscape' ? 'landscape' : 'portrait';
        const basePreset = CANVAS_PRESETS[format] || CANVAS_PRESETS.A4;
        let dimensions = layout?.dimensions && layout.dimensions.width && layout.dimensions.height
            ? { ...layout.dimensions }
            : { ...basePreset };

        if (orientation === 'landscape' && dimensions.height > dimensions.width) {
            dimensions = { width: dimensions.height, height: dimensions.width };
        } else if (orientation === 'portrait' && dimensions.width > dimensions.height) {
            dimensions = { width: dimensions.height, height: dimensions.width };
        }

        state.format = format;
        state.orientation = orientation;
        state.layout = { ...layout, format, orientation, dimensions: { ...dimensions } };
        updateCanvasControls();
        applyCanvasDimensions();
        updateCanvasSizeLabel();
    }

    function setCanvasFormat(format, orientation = state.orientation) {
        const preset = CANVAS_PRESETS[format] || CANVAS_PRESETS.A4;
        state.format = format;
        state.orientation = orientation === 'landscape' ? 'landscape' : 'portrait';
        const base = { ...preset };
        const dims = state.orientation === 'landscape'
            ? { width: base.height, height: base.width }
            : { width: base.width, height: base.height };
        state.layout = {
            ...state.layout,
            format: state.format,
            orientation: state.orientation,
            dimensions: dims,
        };
        applyCanvasDimensions();
        updateCanvasControls();
        updateCanvasSizeLabel();
    }

    function applyCanvasDimensions() {
        const dims = state.layout?.dimensions || CANVAS_PRESETS[state.format] || CANVAS_PRESETS.A4;
        document.documentElement.style.setProperty('--canvas-width', `${dims.width}px`);
        document.documentElement.style.setProperty('--canvas-height', `${dims.height}px`);
        scheduleCanvasFit();
        centerCanvasInViewport();
    }

    function centerCanvasInViewport() {
        if (!els.canvasPanel || !els.canvasWrapper) return;
        requestAnimationFrame(() => {
            if (!els.canvasPanel || !els.canvasWrapper) return;
            const panel = els.canvasPanel;
            const targetLeft = Math.max(0, (panel.scrollWidth - panel.clientWidth) / 2);
            const targetTop = Math.max(0, (panel.scrollHeight - panel.clientHeight) / 2);
            if (Math.abs(panel.scrollLeft - targetLeft) > 1) {
                panel.scrollLeft = targetLeft;
            }
            if (Math.abs(panel.scrollTop - targetTop) > 1) {
                panel.scrollTop = targetTop;
            }
        });
    }

    function updateCanvasControls() {
        if (els.canvasFormat) {
            els.canvasFormat.value = state.format;
        }
        if (els.toggleOrientation) {
            els.toggleOrientation.textContent = state.orientation === 'portrait' ? '↺' : '↻';
            els.toggleOrientation.setAttribute('aria-label', `Toggle orientation (currently ${state.orientation})`);
            els.toggleOrientation.title = `Toggle orientation (currently ${state.orientation})`;
        }
    }

    function updateCanvasSizeLabel() {
        const dims = state.layout?.dimensions || CANVAS_PRESETS[state.format] || CANVAS_PRESETS.A4;
        const orientationLabel = state.orientation === 'landscape' ? 'Landscape' : 'Portrait';
        if (els.canvasSizeLabel) {
            els.canvasSizeLabel.textContent = `${dims.width} × ${dims.height} px · ${orientationLabel}`;
        }
        if (els.zoomLabel) {
            els.zoomLabel.textContent = `${Math.round(state.zoom * 100)}%`;
        }
    }

    function triggerImageUpload(blockId) {
        const block = state.blocks.get(blockId);
        if (!block || !els.imageUploadInput) return;
        state.pendingImageBlock = {
            blockId,
            pageId: getPageIdForBlock(blockId),
        };
        els.imageUploadInput.value = '';
        els.imageUploadInput.click();
    }

    async function handleImageUploadSelection(event) {
        const input = event.target;
        if (!input.files || !input.files.length || !state.pendingImageBlock) {
            state.pendingImageBlock = null;
            return;
        }
        const file = input.files[0];
        input.value = '';
        const { blockId } = state.pendingImageBlock;
        state.pendingImageBlock = null;
        const { block } = findBlockInPages(blockId);
        if (!block) {
            showToast('Block unavailable', true);
            return;
        }

        if (!file.type.startsWith('image/')) {
            showToast('Please select an image file', true);
            return;
        }

        try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('project', state.project);
            formData.append('block_id', blockId);
            formData.append('filename', file.name);

            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData,
            });
            if (!response.ok) {
                const detail = await safeReadText(response);
                throw new Error(detail || `Upload failed (${response.status})`);
            }
            const data = await response.json();
            if (!data.success || !data.url) {
                throw new Error(data.error || 'Upload failed');
            }

            block.imageUrl = data.url;
            if (!block.content || block.content === '[Image]' || block.content === 'Double-click to add image') {
                block.content = file.name;
            }
            applyBlockContent(block);
            persistBlock(block.id, { imageUrl: block.imageUrl, content: block.content });
            showToast('Image uploaded');
        } catch (error) {
            console.error(error);
            showToast(error.message || 'Unable to upload image', true);
        }
    }

    function initChatInterface() {
        if (!els.chatLauncher || !els.chatPanel) return;
        if (!state.chat.messages.length) {
            pushChatMessage({
                role: 'assistant',
                content: 'Hi! I can answer layout questions, attach canvas snapshots, or read your files when Agent Mode is on.',
            });
        }
        els.chatLauncher.addEventListener('click', () => toggleChatPanel(!state.chat.open));
        if (els.chatClose) {
            els.chatClose.addEventListener('click', () => toggleChatPanel(false));
        }
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && state.chat.open) {
                toggleChatPanel(false);
            }
        });
        if (els.chatForm) {
            els.chatForm.addEventListener('submit', handleChatSubmit);
        }
        if (els.chatAttachCanvas) {
            els.chatAttachCanvas.addEventListener('click', attachCanvasSnapshot);
        }
        if (els.chatAgentToggle) {
            els.chatAgentToggle.addEventListener('click', toggleAgentMode);
        }
        initChatResizeHandle();
        setChatStatus('Assistant ready');
        updateAgentToggle();
    }

    function toggleChatPanel(forceOpen) {
        if (!els.chatPanel || !els.chatLauncher) return;
        const open = typeof forceOpen === 'boolean' ? forceOpen : !state.chat.open;
        state.chat.open = open;
        els.chatPanel.classList.toggle('chat-panel--open', open);
        els.chatPanel.setAttribute('aria-hidden', open ? 'false' : 'true');
        els.chatLauncher.setAttribute('aria-expanded', open ? 'true' : 'false');
        if (open) {
            applySavedChatPanelSize();
            renderChatMessages();
            scrollChatLogToBottom();
        }
    }

    function initChatResizeHandle() {
        if (!els.chatResizeHandle) return;
        els.chatResizeHandle.addEventListener('pointerdown', startChatResize);
    }

    function startChatResize(event) {
        if (!els.chatPanel) return;
        event.preventDefault();
        event.stopPropagation();
        const rect = els.chatPanel.getBoundingClientRect();
        chatResizeSession.active = true;
        chatResizeSession.pointerId = event.pointerId ?? null;
        chatResizeSession.startX = event.clientX;
        chatResizeSession.startY = event.clientY;
        chatResizeSession.startWidth = rect.width;
        chatResizeSession.startHeight = rect.height;
        state.chat.resizing = true;
        els.chatPanel.classList.add('chat-panel--resizing');
        if (els.chatResizeHandle && typeof els.chatResizeHandle.setPointerCapture === 'function' && Number.isInteger(event.pointerId)) {
            try {
                els.chatResizeHandle.setPointerCapture(event.pointerId);
            } catch (error) {
                console.warn('Unable to capture pointer:', error);
            }
        }
        document.addEventListener('pointermove', handleChatResizeMove);
        document.addEventListener('pointerup', endChatResize);
        document.addEventListener('pointercancel', endChatResize);
    }

    function handleChatResizeMove(event) {
        if (!chatResizeSession.active || !els.chatPanel) return;
        event.preventDefault();
        const deltaX = chatResizeSession.startX - event.clientX;
        const deltaY = chatResizeSession.startY - event.clientY;
        const nextWidth = chatResizeSession.startWidth + deltaX;
        const nextHeight = chatResizeSession.startHeight + deltaY;
        setChatPanelSize(nextWidth, nextHeight);
    }

    function endChatResize(event) {
        if (!chatResizeSession.active) return;
        chatResizeSession.active = false;
        document.removeEventListener('pointermove', handleChatResizeMove);
        document.removeEventListener('pointerup', endChatResize);
        document.removeEventListener('pointercancel', endChatResize);
        if (els.chatPanel) {
            els.chatPanel.classList.remove('chat-panel--resizing');
        }
        if (els.chatResizeHandle && typeof els.chatResizeHandle.releasePointerCapture === 'function' && Number.isInteger(chatResizeSession.pointerId)) {
            try {
                els.chatResizeHandle.releasePointerCapture(chatResizeSession.pointerId);
            } catch (error) {
                console.warn('Unable to release pointer:', error);
            }
        }
        chatResizeSession.pointerId = null;
        state.chat.resizing = false;
    }

    function setChatPanelSize(width, height) {
        if (!els.chatPanel) return;
        const rect = els.chatPanel.getBoundingClientRect();
        const targetWidth = Number.isFinite(width) ? width : rect.width;
        const targetHeight = Number.isFinite(height) ? height : rect.height;
        const clamped = clampChatPanelSize(targetWidth, targetHeight);
        els.chatPanel.style.width = `${clamped.width}px`;
        els.chatPanel.style.height = `${clamped.height}px`;
        state.chat.panelSize = { width: clamped.width, height: clamped.height };
        return clamped;
    }

    function clampChatPanelSize(width, height) {
        const availableWidthRaw = window.innerWidth - 32;
        const availableHeightRaw = window.innerHeight * 0.85;
        const widthCeiling = availableWidthRaw > 0 ? availableWidthRaw : CHAT_PANEL_MIN_WIDTH;
        const heightCeiling = availableHeightRaw > 0 ? availableHeightRaw : CHAT_PANEL_MIN_HEIGHT;
        const minWidth = availableWidthRaw > 0 ? Math.min(CHAT_PANEL_MIN_WIDTH, availableWidthRaw) : CHAT_PANEL_MIN_WIDTH;
        const minHeight = availableHeightRaw > 0 ? Math.min(CHAT_PANEL_MIN_HEIGHT, availableHeightRaw) : CHAT_PANEL_MIN_HEIGHT;
        const maxWidth = Math.max(minWidth, Math.min(CHAT_PANEL_MAX_WIDTH, widthCeiling));
        const maxHeight = Math.max(minHeight, Math.min(CHAT_PANEL_MAX_HEIGHT, heightCeiling));
        return {
            width: Math.min(Math.max(width, minWidth), maxWidth),
            height: Math.min(Math.max(height, minHeight), maxHeight),
        };
    }

    function applySavedChatPanelSize() {
        if (!els.chatPanel) return;
        if (!state.chat.panelSize) {
            els.chatPanel.style.width = '';
            els.chatPanel.style.height = '';
            return;
        }
        setChatPanelSize(state.chat.panelSize.width, state.chat.panelSize.height);
    }

    function handleChatPanelBounds() {
        if (!state.chat.panelSize) return;
        setChatPanelSize(state.chat.panelSize.width, state.chat.panelSize.height);
    }

    async function handleChatSubmit(event) {
        event.preventDefault();
        if (state.chat.sending) return;
        const text = (els.chatInput?.value || '').trim();
        if (text.toLowerCase() === '/terminal') {
            if (els.chatInput) {
                els.chatInput.value = '';
            }
            state.chat.pendingAttachments = [];
            renderPendingAttachments();
            openFloatingTerminal();
            pushChatMessage({
                role: 'system',
                content: 'Opened the floating terminal window. Drag it anywhere on the canvas and close it when finished.',
            });
            return;
        }
        const attachments = state.chat.pendingAttachments.slice();
        if (!text && attachments.length === 0 && !state.chat.agentEnabled) {
            showToast('Type a message, attach a PNG, or enable Agent Mode before sending.', true);
            return;
        }
        if (els.chatInput) {
            els.chatInput.value = '';
        }
        const userContent = text || (attachments.length ? 'Shared attachments.' : state.chat.agentEnabled ? 'Shared agent context.' : '…');
        pushChatMessage({
            role: 'user',
            content: userContent,
            attachments: attachments.map((att) => ({ ...att })),
        });
        state.chat.pendingAttachments = [];
        renderPendingAttachments();
        await sendMessageToAssistant(text, attachments);
    }

    async function sendMessageToAssistant(text, attachments) {
        state.chat.sending = true;
        setChatStatus('Contacting assistant…');
        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    project: state.project,
                    message: text,
                    attachments: attachments.map((att) => ({
                        type: att.type,
                        label: att.label,
                        dataUrl: att.dataUrl,
                        meta: att.meta,
                    })),
                    agentMode: state.chat.agentEnabled,
                    agentSnapshot: state.chat.agentSnapshot,
                }),
            });
            if (!response.ok) {
                throw new Error((await safeReadText(response)) || 'Assistant request failed.');
            }
            const data = await response.json();
            const replyAttachments = [];
            if (data.agentSnapshot) {
                if (!state.chat.agentSnapshot) {
                    state.chat.agentSnapshot = data.agentSnapshot;
                }
                if (data.agentSnapshot.tree) {
                    replyAttachments.push({
                        id: `ctx-${Date.now()}`,
                        type: 'context',
                        label: 'Project tree',
                        content: String(data.agentSnapshot.tree).slice(0, CHAT_TREE_PREVIEW_LIMIT),
                    });
                }
                if (data.agentSnapshot.layout) {
                    const layoutJson = JSON.stringify(data.agentSnapshot.layout, null, 2);
                    replyAttachments.push({
                        id: `layout-${Date.now()}`,
                        type: 'json',
                        label: 'Layout JSON',
                        content: layoutJson.slice(0, CHAT_LAYOUT_PREVIEW_LIMIT),
                    });
                }
            }
            pushChatMessage({
                role: 'assistant',
                content: data.reply || 'I received your message.',
                attachments: replyAttachments,
            });
            setChatStatus('Assistant ready');
        } catch (error) {
            console.error(error);
            pushChatMessage({
                role: 'system',
                content: error.message || 'Unable to reach the assistant.',
            });
            showToast(error.message || 'Assistant unavailable', true);
            setChatStatus('Assistant unavailable');
        } finally {
            state.chat.sending = false;
        }
    }

    function pushChatMessage(message) {
        const payload = {
            id: `msg-${Date.now()}-${Math.random().toString(16).slice(2)}`,
            role: message.role || 'assistant',
            content: message.content || '',
            attachments: (message.attachments || []).map((att) => ({ ...att })),
        };
        state.chat.messages.push(payload);
        if (state.chat.messages.length > 200) {
            state.chat.messages = state.chat.messages.slice(-200);
        }
        renderChatMessages();
    }

    function renderChatMessages() {
        if (!els.chatLog) return;
        els.chatLog.innerHTML = '';
        state.chat.messages.forEach((message) => {
            const wrapper = document.createElement('div');
            wrapper.className = `chat-message chat-message--${message.role}`;
            const bubble = document.createElement('div');
            bubble.className = 'chat-message__bubble';
            const textEl = document.createElement('div');
            textEl.className = 'chat-message__text';
            textEl.textContent = message.content || '';
            bubble.appendChild(textEl);
            if (message.attachments && message.attachments.length) {
                const attachmentsEl = document.createElement('div');
                attachmentsEl.className = 'chat-message__attachments';
                message.attachments.forEach((attachment) => {
                    attachmentsEl.appendChild(renderMessageAttachment(attachment));
                });
                bubble.appendChild(attachmentsEl);
            }
            wrapper.appendChild(bubble);
            els.chatLog.appendChild(wrapper);
        });
        scrollChatLogToBottom();
    }

    function renderMessageAttachment(attachment) {
        const card = document.createElement('div');
        card.className = 'chat-message__attachment';
        const label = document.createElement('div');
        label.className = 'chat-message__attachment-label';
        label.textContent = attachment.label || attachment.type || 'Attachment';
        card.appendChild(label);
        if (attachment.type === 'image' && attachment.dataUrl) {
            const img = document.createElement('img');
            img.src = attachment.dataUrl;
            img.alt = attachment.label || 'Attached image';
            img.loading = 'lazy';
            card.appendChild(img);
        } else if (attachment.content) {
            const pre = document.createElement('pre');
            pre.textContent = attachment.content;
            card.appendChild(pre);
        }
        return card;
    }

    async function attachCanvasSnapshot() {
        if (state.chat.pendingAttachments.length >= CHAT_ATTACHMENT_LIMIT) {
            showToast(`Maximum of ${CHAT_ATTACHMENT_LIMIT} attachments per message.`, true);
            return;
        }
        toggleChatPanel(true);
        setChatStatus('Rendering PNG…');
        try {
            const response = await fetch('/api/chat/attachments/canvas', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project: state.project }),
            });
            if (!response.ok) {
                throw new Error((await safeReadText(response)) || 'Unable to export PNG');
            }
            const data = await response.json();
            const attachment = data.attachment;
            state.chat.pendingAttachments.push({
                id: ++chatAttachmentId,
                type: 'image',
                label: attachment.label || 'layout.png',
                dataUrl: attachment.dataUrl,
                meta: { width: attachment.width, height: attachment.height },
            });
            renderPendingAttachments();
            showToast('Attached current canvas snapshot');
        } catch (error) {
            console.error(error);
            showToast(error.message || 'Unable to capture layout', true);
        } finally {
            setChatStatus('Assistant ready');
        }
    }

    function renderPendingAttachments() {
        if (!els.chatAttachments) return;
        const items = state.chat.pendingAttachments;
        els.chatAttachments.innerHTML = '';
        if (!items.length) {
            els.chatAttachments.hidden = true;
            return;
        }
        els.chatAttachments.hidden = false;
        items.forEach((attachment) => {
            const chip = document.createElement('div');
            chip.className = 'chat-attachment-chip';
            const label = document.createElement('span');
            label.textContent = attachment.label || attachment.type;
            chip.appendChild(label);
            const remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'chat-attachment-chip__remove';
            remove.setAttribute('aria-label', 'Remove attachment');
            remove.textContent = '×';
            remove.addEventListener('click', () => removePendingAttachment(attachment.id));
            chip.appendChild(remove);
            els.chatAttachments.appendChild(chip);
        });
    }

    function removePendingAttachment(id) {
        state.chat.pendingAttachments = state.chat.pendingAttachments.filter((att) => att.id !== id);
        renderPendingAttachments();
    }

    function openFloatingTerminal() {
        const terminal = ensureTerminalWindow();
        if (!terminal) return;
        terminal.classList.add('floating-terminal--visible');
        state.terminal.isOpen = true;
        constrainTerminalToViewport();
        if (state.terminal.input) {
            state.terminal.input.focus();
            state.terminal.input.select();
        }
    }

    function closeFloatingTerminal() {
        if (!state.terminal.element) return;
        state.terminal.element.classList.remove('floating-terminal--visible');
        state.terminal.isOpen = false;
    }

    function ensureTerminalWindow() {
        if (state.terminal.element) return state.terminal.element;
        const container = document.createElement('section');
        container.className = 'floating-terminal';
        container.setAttribute('role', 'dialog');
        container.setAttribute('aria-label', 'Fyona terminal');
        container.style.left = '72px';
        container.style.top = '120px';

        const header = document.createElement('div');
        header.className = 'floating-terminal__header';

        const traffic = document.createElement('div');
        traffic.className = 'floating-terminal__traffic';
        const closeBtn = document.createElement('button');
        closeBtn.type = 'button';
        closeBtn.className = 'floating-terminal__dot floating-terminal__dot--close';
        closeBtn.setAttribute('aria-label', 'Close terminal');
        closeBtn.addEventListener('click', closeFloatingTerminal);
        traffic.appendChild(closeBtn);
        const minimize = document.createElement('span');
        minimize.className = 'floating-terminal__dot floating-terminal__dot--min';
        traffic.appendChild(minimize);
        const expand = document.createElement('span');
        expand.className = 'floating-terminal__dot floating-terminal__dot--max';
        traffic.appendChild(expand);
        header.appendChild(traffic);

        const title = document.createElement('div');
        title.className = 'floating-terminal__title';
        title.textContent = 'Fyona Terminal';
        header.appendChild(title);

        header.addEventListener('pointerdown', handleTerminalDragStart);

        const body = document.createElement('div');
        body.className = 'floating-terminal__body';

        const log = document.createElement('div');
        log.className = 'floating-terminal__log';
        body.appendChild(log);

        const promptForm = document.createElement('form');
        promptForm.className = 'floating-terminal__prompt';
        const caret = document.createElement('span');
        caret.className = 'floating-terminal__caret';
        caret.textContent = '$';
        promptForm.appendChild(caret);
        const input = document.createElement('input');
        input.type = 'text';
        input.placeholder = 'Type a command…';
        input.autocomplete = 'off';
        input.spellcheck = false;
        promptForm.appendChild(input);
        promptForm.addEventListener('submit', (event) => {
            event.preventDefault();
            const value = input.value.trim();
            if (!value) return;
            appendTerminalLine(`$ ${value}`, 'input');
            appendTerminalLine('Command output placeholder — wire this up when ready.', 'muted');
            input.value = '';
        });
        body.appendChild(promptForm);

        container.appendChild(header);
        container.appendChild(body);
        document.body.appendChild(container);

        state.terminal.element = container;
        state.terminal.log = log;
        state.terminal.input = input;

        appendTerminalLine('Fyona terminal ready.', 'muted');
        appendTerminalLine('Commands will run line-by-line once connected.', 'muted');
        return container;
    }

    function appendTerminalLine(text, variant = 'output') {
        if (!state.terminal.log) return;
        const line = document.createElement('div');
        line.className = `floating-terminal__line floating-terminal__line--${variant}`;
        line.textContent = text;
        state.terminal.log.appendChild(line);
        state.terminal.log.scrollTop = state.terminal.log.scrollHeight;
    }

    function handleTerminalDragStart(event) {
        if (!state.terminal.element) return;
        if (event.target.closest('button')) return;
        if (event.pointerType === 'mouse' && event.button !== 0) return;
        event.preventDefault();
        state.terminal.dragging = true;
        state.terminal.dragOffsetX = event.clientX - state.terminal.element.offsetLeft;
        state.terminal.dragOffsetY = event.clientY - state.terminal.element.offsetTop;
        state.terminal.element.classList.add('floating-terminal--dragging');
        window.addEventListener('pointermove', handleTerminalDragMove);
        window.addEventListener('pointerup', handleTerminalDragEnd);
    }

    function handleTerminalDragMove(event) {
        if (!state.terminal.dragging || !state.terminal.element) return;
        event.preventDefault();
        positionTerminal(event.clientX - state.terminal.dragOffsetX, event.clientY - state.terminal.dragOffsetY);
    }

    function handleTerminalDragEnd() {
        if (!state.terminal.dragging) return;
        state.terminal.dragging = false;
        if (state.terminal.element) {
            state.terminal.element.classList.remove('floating-terminal--dragging');
        }
        window.removeEventListener('pointermove', handleTerminalDragMove);
        window.removeEventListener('pointerup', handleTerminalDragEnd);
    }

    function positionTerminal(left, top) {
        if (!state.terminal.element) return;
        const margin = 12;
        const maxLeft = window.innerWidth - state.terminal.element.offsetWidth - margin;
        const maxTop = window.innerHeight - state.terminal.element.offsetHeight - margin;
        const clampedLeft = Math.min(Math.max(margin, left), Math.max(margin, maxLeft));
        const clampedTop = Math.min(Math.max(margin, top), Math.max(margin, maxTop));
        state.terminal.element.style.left = `${clampedLeft}px`;
        state.terminal.element.style.top = `${clampedTop}px`;
    }

    function constrainTerminalToViewport() {
        if (!state.terminal.element || !state.terminal.isOpen) return;
        const rect = state.terminal.element.getBoundingClientRect();
        positionTerminal(rect.left, rect.top);
    }

    async function toggleAgentMode() {
        if (state.chat.agentEnabled) {
            state.chat.agentEnabled = false;
            state.chat.agentSnapshot = null;
            updateAgentToggle();
            pushChatMessage({
                role: 'system',
                content: 'Agent Mode disabled. I will only use chat messages unless you re-enable it.',
            });
            updateChatProjectStatus();
            return;
        }
        toggleChatPanel(true);
        const button = els.chatAgentToggle;
        if (button) {
            button.disabled = true;
            button.classList.add('is-loading');
        }
        setChatStatus('Collecting project tree…');
        try {
            const response = await fetch(`/api/chat/agent-snapshot?project=${encodeURIComponent(state.project)}`);
            if (!response.ok) {
                throw new Error((await safeReadText(response)) || 'Unable to inspect project structure.');
            }
            const data = await response.json();
            state.chat.agentEnabled = true;
            state.chat.agentSnapshot = data.snapshot;
            pushChatMessage({
                role: 'system',
                content: 'Agent Mode enabled. The assistant can now inspect the project directory and layout JSON.',
                attachments: [
                    {
                        id: `agent-${Date.now()}`,
                        type: 'context',
                        label: 'Project tree',
                        content: String(data.snapshot?.tree || '').slice(0, CHAT_TREE_PREVIEW_LIMIT),
                    },
                ],
            });
            setChatStatus('Agent Mode enabled');
        } catch (error) {
            console.error(error);
            showToast(error.message || 'Unable to enable Agent Mode', true);
            setChatStatus('Assistant unavailable');
        } finally {
            if (button) {
                button.disabled = false;
                button.classList.remove('is-loading');
            }
            updateAgentToggle();
        }
    }

    function updateAgentToggle() {
        if (!els.chatAgentToggle) return;
        els.chatAgentToggle.classList.toggle('is-active', !!state.chat.agentEnabled);
        els.chatAgentToggle.textContent = state.chat.agentEnabled ? 'Agent Mode On' : 'Agent Mode Off';
        if (els.chatAgentIndicator) {
            els.chatAgentIndicator.hidden = !state.chat.agentEnabled;
        }
    }

    function setChatStatus(text) {
        if (!els.chatStatus) return;
        els.chatStatus.textContent = text;
    }

    function updateChatProjectStatus() {
        if (state.chat.sending) return;
        setChatStatus(`Ready · Project “${state.project}”`);
    }

    function scrollChatLogToBottom() {
        if (!els.chatLog) return;
        requestAnimationFrame(() => {
            if (els.chatLog) {
                els.chatLog.scrollTop = els.chatLog.scrollHeight;
            }
        });
    }

    async function safeReadText(response) {
        try {
            return await response.text();
        } catch {
            return '';
        }
    }

});
