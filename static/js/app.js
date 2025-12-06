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
        inspectorFontSize: document.getElementById('inspector-font-size'),
        inspectorLeft: document.getElementById('inspector-left'),
        inspectorTop: document.getElementById('inspector-top'),
        inspectorWidth: document.getElementById('inspector-width'),
        inspectorHeight: document.getElementById('inspector-height'),
        inspectorBg: document.getElementById('inspector-bg'),
        inspectorFg: document.getElementById('inspector-fg'),
        inspectorRadius: document.getElementById('inspector-radius'),
        inspectorMarginTop: document.getElementById('inspector-margin-top'),
        inspectorMarginRight: document.getElementById('inspector-margin-right'),
        inspectorMarginBottom: document.getElementById('inspector-margin-bottom'),
        inspectorMarginLeft: document.getElementById('inspector-margin-left'),
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
        chatBackdrop: document.getElementById('chat-backdrop'),
        chatClose: document.getElementById('chat-close'),
        chatLog: document.getElementById('chat-log'),
        chatForm: document.getElementById('chat-form'),
        chatInput: document.getElementById('chat-input'),
        chatAttachCanvas: document.getElementById('chat-attach-canvas'),
        chatAttachments: document.getElementById('chat-attachments'),
        chatStatus: document.getElementById('chat-status'),
        chatProgress: document.getElementById('chat-progress'),
        chatIntent: document.getElementById('chat-intent'),
        chatIntentCopy: document.getElementById('chat-intent-copy'),
        chatIntentPalette: document.getElementById('chat-intent-palette'),
        chatAgentToggle: document.getElementById('chat-agent-toggle'),
        chatAgentIndicator: document.getElementById('chat-agent-indicator'),
        chatAgentAllowEdits: document.getElementById('chat-agent-allow-edits'),
        chatAgentAllowWeb: document.getElementById('chat-agent-allow-web'),
        chatAgentPermissionSummary: document.getElementById('chat-agent-permission-summary'),
        chatAgentOptionsToggle: document.getElementById('chat-agent-options-toggle'),
        chatAgentViewMode: document.getElementById('chat-agent-view-mode'),
        chatResizeHandle: document.getElementById('chat-resize-handle'),
        chatTokenStats: document.getElementById('chat-token-stats'),
        chatProgressbar: document.getElementById('chat-progressbar'),
        chatProgressbarFill: document.getElementById('chat-progressbar-fill'),
        chatProgressbarLabel: document.getElementById('chat-progressbar-label'),
    };

    const fyonaConfig = window.FYONA_CONFIG || {};

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
        pageMenu: {
            element: null,
            open: false,
            pageId: null,
            anchor: null,
        },
        chat: {
            open: false,
            messages: [],
            pendingAttachments: [],
            sending: false,
            agentEnabled: false,
            agentSnapshot: null,
            agentCanEdit: false,
            agentAllowWeb: false,
            agentViewMode: 'document', // Default to document mode
            optionsOpen: false,
            bingSearchAvailable: !!fyonaConfig.bingSearchAvailable,
            panelSize: null,
            resizing: false,
            progress: {
                id: null,
                timer: null,
                messageId: null,
                lastStatus: null,
                historyLength: 0,
                events: [],
            },
        },
        terminal: {
            element: null,
            log: null,
            input: null,
            dragging: false,
            dragOffsetX: 0,
            dragOffsetY: 0,
            isOpen: false,
            isBusy: false,
        },
        agentHighlightQueue: [],
        agentHighlightActive: false,
        tokenStats: {
            sessionTokens: 0,
            lifetimeTokens: 0,
            sessionImages: 0,
            lifetimeImages: 0,
        },
    };

    const FONT_OPTIONS = [
        { value: 'inter', label: 'Inter', css: '"Inter", "Helvetica Neue", Arial, sans-serif' },
        { value: 'space-grotesk', label: 'Space Grotesk', css: '"Space Grotesk", "Inter", "Helvetica Neue", sans-serif' },
        { value: 'playfair', label: 'Playfair Display', css: '"Playfair Display", "Times New Roman", serif' },
        { value: 'merriweather', label: 'Merriweather', css: '"Merriweather", Georgia, serif' },
    ];

    const DEFAULT_FONT_VALUE = FONT_OPTIONS[0].value;
    const DEFAULT_FONT_SIZE = 16;
    const FONT_SIZE_LIMITS = { min: 8, max: 200 };
    const DEFAULT_MARGINS = {
        text: { top: 16, right: 16, bottom: 16, left: 16 },
        image: { top: 0, right: 0, bottom: 0, left: 0 },
    };
    const MARGIN_LIMITS = { min: 0, max: 480 };

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
    const PAGE_THUMB_BLOCK_LIMIT = 20;
    const PAGE_MENU_ACTIONS = [
        { id: 'rename', label: 'Rename page' },
        { id: 'duplicate', label: 'Duplicate page' },
        { id: 'copy', label: 'Copy to clipboard' },
        { id: 'delete', label: 'Delete page', tone: 'danger' },
    ];
    const LAYOUT_SYNC_DELAY = 600;
    const CHAT_PANEL_MIN_WIDTH = 260;
    const CHAT_PANEL_MAX_WIDTH = 640;
    const CHAT_PANEL_MIN_HEIGHT = 260;
    const CHAT_PANEL_MAX_HEIGHT = 640;
    const CHAT_TRACE_STEP_LIMIT = 200;
    const CHAT_TRACE_TEXT_LIMIT = 260;
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
        renderTokenStats();
        configureZoomControl();
        initFontOptions();
        initToolbarTabs();
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
        await loadTokenStats();
        renderDesignIntent();
        setChatProgressBar({ active: false });
    }

    function configureZoomControl() {
        if (!els.canvasZoom) return;
        els.canvasZoom.min = ZOOM_CONFIG.min;
        els.canvasZoom.max = ZOOM_CONFIG.max;
        els.canvasZoom.step = ZOOM_CONFIG.step;
        els.canvasZoom.value = state.zoom;
    }

    function initToolbarTabs() {
        const tabs = Array.from(document.querySelectorAll('.toolbar__tab'));
        const sections = Array.from(document.querySelectorAll('.toolbar__section'));
        if (!tabs.length || !sections.length) return;

        const activate = (targetId) => {
            if (!targetId) return;
            tabs.forEach((tab) => {
                const isActive = tab.dataset.target === targetId;
                tab.classList.toggle('is-active', isActive);
                tab.setAttribute('aria-selected', isActive ? 'true' : 'false');
                tab.setAttribute('tabindex', isActive ? '0' : '-1');
            });
            sections.forEach((section) => {
                const match = section.id === targetId;
                section.classList.toggle('toolbar__section--active', match);
                if (match) {
                    section.removeAttribute('hidden');
                } else {
                    section.setAttribute('hidden', 'hidden');
                }
            });
        };

        tabs.forEach((tab, index) => {
            if (!tab.hasAttribute('tabindex')) {
                tab.setAttribute('tabindex', index === 0 ? '0' : '-1');
            }
            tab.addEventListener('click', () => activate(tab.dataset.target));
            tab.addEventListener('keydown', (event) => {
                if (event.key !== 'Enter' && event.key !== ' ') return;
                event.preventDefault();
                activate(tab.dataset.target);
            });
        });

        const firstActive = tabs.find((tab) => tab.classList.contains('is-active')) || tabs[0];
        if (firstActive) {
            activate(firstActive.dataset.target);
        }
    }

    function initPageMenu() {
        const menu = document.createElement('div');
        menu.className = 'page-menu';
        menu.hidden = true;

        const list = document.createElement('div');
        list.className = 'page-menu__list';
        PAGE_MENU_ACTIONS.forEach((action) => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'page-menu__item';
            if (action.tone === 'danger') {
                btn.classList.add('page-menu__item--danger');
            }
            btn.dataset.action = action.id;
            btn.textContent = action.label;
            btn.addEventListener('click', () => {
                handlePageMenuAction(action.id);
            });
            list.appendChild(btn);
        });

        menu.appendChild(list);
        document.body.appendChild(menu);
        state.pageMenu.element = menu;

        document.addEventListener('click', (event) => {
            if (!state.pageMenu.open || !state.pageMenu.element) return;
            const anchor = state.pageMenu.anchor;
            if (!state.pageMenu.element.contains(event.target) && !(anchor && anchor.contains(event.target))) {
                closePageMenu();
            }
        });
        document.addEventListener('contextmenu', (event) => {
            if (!state.pageMenu.open || !state.pageMenu.element) return;
            const anchor = state.pageMenu.anchor;
            if (!state.pageMenu.element.contains(event.target) && !(anchor && anchor.contains(event.target))) {
                closePageMenu();
            }
        });
        document.addEventListener('keydown', (event) => {
            if (!state.pageMenu.open) return;
            if (event.key === 'Escape') {
                event.preventDefault();
                closePageMenu();
            }
        });
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

        if (els.inspectorFontSize) {
            const handleFontSizeUpdate = (persist) => {
                const block = getSelectedBlock();
                if (!block || block.type === 'image') return;
                const value = normalizeFontSizeValue(els.inspectorFontSize.value);
                block.typography = { ...(block.typography || {}), fontSize: value };
                els.inspectorFontSize.value = value;
                applyBlockTypography(block);
                if (persist) {
                    persistBlock(block.id, { typography: { ...block.typography } });
                }
            };
            els.inspectorFontSize.addEventListener('input', () => handleFontSizeUpdate(false));
            els.inspectorFontSize.addEventListener('change', () => handleFontSizeUpdate(true));
        }

        bindNumericInput(els.inspectorLeft, 'left');
        bindNumericInput(els.inspectorTop, 'top');
        bindNumericInput(els.inspectorWidth, 'width', 40);
        bindNumericInput(els.inspectorHeight, 'height', 40);
        bindMarginInput(els.inspectorMarginTop, 'top');
        bindMarginInput(els.inspectorMarginRight, 'right');
        bindMarginInput(els.inspectorMarginBottom, 'bottom');
        bindMarginInput(els.inspectorMarginLeft, 'left');

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

    function bindMarginInput(input, side) {
        if (!input) return;
        const updateMargin = (persist) => {
            const block = getSelectedBlock();
            if (!block) return;
            const margin = ensureBlockMargin(block);
            const value = normalizeMarginValue(input.value, margin[side]);
            margin[side] = value;
            block.margin = { ...margin };
            input.value = value;
            applyBlockAppearance(block);
            if (persist) {
                persistBlock(block.id, { margin: { ...block.margin } });
            }
        };
        input.addEventListener('input', () => updateMargin(false));
        input.addEventListener('change', () => updateMargin(true));
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

    async function loadTokenStats() {
        try {
            const response = await fetch('/api/chat/token-stats');
            if (!response.ok) throw new Error('Failed to fetch token stats');
            const data = await response.json();
            if (data.success && data.stats) {
                updateTokenStats(data.stats);
            }
        } catch (error) {
            console.warn('Unable to load token stats', error);
        }
    }

    function updateTokenStats(stats) {
        if (!stats) return;
        state.tokenStats = {
            sessionTokens: stats.sessionTokens ?? state.tokenStats.sessionTokens,
            lifetimeTokens: stats.lifetimeTokens ?? state.tokenStats.lifetimeTokens,
            sessionImages: stats.sessionImages ?? state.tokenStats.sessionImages,
            lifetimeImages: stats.lifetimeImages ?? state.tokenStats.lifetimeImages,
        };
        renderTokenStats();
    }

    function renderTokenStats() {
        if (!els.chatTokenStats) return;
        const stats = state.tokenStats;
        if (!stats) {
            els.chatTokenStats.textContent = 'Tokens: —';
            return;
        }
        const sessionTokens = stats.sessionTokens ?? 0;
        const lifetimeTokens = stats.lifetimeTokens ?? 0;
        const sessionImages = formatBytes(stats.sessionImages ?? 0);
        const lifetimeImages = formatBytes(stats.lifetimeImages ?? 0);
        els.chatTokenStats.textContent = `Session tokens: ${sessionTokens.toLocaleString()} • Total: ${lifetimeTokens.toLocaleString()} • Images: ${sessionImages} (Total ${lifetimeImages})`;
    }

    function formatBytes(bytes) {
        const value = Number(bytes) || 0;
        if (value <= 0) return '0 B';
        const units = ['B', 'KB', 'MB', 'GB'];
        let index = 0;
        let sized = value;
        while (sized >= 1024 && index < units.length - 1) {
            sized /= 1024;
            index += 1;
        }
        return `${sized >= 10 ? Math.round(sized) : sized.toFixed(1)} ${units[index]}`;
    }

    async function loadLayout(project) {
        const previousProject = state.project;
        try {
            const response = await fetch(`/api/layout?project=${encodeURIComponent(project)}`);
            if (!response.ok) throw new Error('Failed to fetch layout');
            const layout = await response.json();

            const newProjectName = layout.project || project;
            const projectChanged = previousProject && previousProject !== newProjectName;
            const agentWasEnabled = state.chat.agentEnabled;
            state.project = newProjectName;
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
            renderDesignIntent();
            if (projectChanged) {
                disableAgentMode({ silent: true });
                if (agentWasEnabled) {
                    showToast(
                        `Agent Mode reset after switching to “${state.project}”. Re-enable it to let Fyona inspect this layout.`,
                    );
                }
            }
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

    function defaultMarginForType(type) {
        const key = typeof type === 'string' && type.toLowerCase() === 'image' ? 'image' : 'text';
        const fallback = DEFAULT_MARGINS[key] || DEFAULT_MARGINS.text;
        return { ...fallback };
    }

    function normalizeMarginValue(value, fallback) {
        const numeric = Math.round(Number(value));
        if (!Number.isFinite(numeric)) {
            return clampNumber(fallback, MARGIN_LIMITS.min, MARGIN_LIMITS.max);
        }
        return clampNumber(numeric, MARGIN_LIMITS.min, MARGIN_LIMITS.max);
    }

    function normalizeMargin(rawMargin, type) {
        const base = defaultMarginForType(type);
        if (rawMargin == null) {
            return base;
        }
        if (typeof rawMargin === 'number' || (typeof rawMargin === 'string' && rawMargin.trim() !== '')) {
            const value = normalizeMarginValue(rawMargin, base.top);
            return { top: value, right: value, bottom: value, left: value };
        }
        if (typeof rawMargin === 'object') {
            const margin = { ...base };
            ['top', 'right', 'bottom', 'left'].forEach((side) => {
                if (side in rawMargin) {
                    margin[side] = normalizeMarginValue(rawMargin[side], margin[side]);
                }
            });
            return margin;
        }
        return base;
    }

    function ensureBlockMargin(block) {
        if (!block.margin || typeof block.margin !== 'object') {
            block.margin = normalizeMargin(null, block.type);
        } else {
            block.margin = normalizeMargin(block.margin, block.type);
        }
        return block.margin;
    }

    function normalizeFontSizeValue(value) {
        const numeric = Number(value);
        if (!Number.isFinite(numeric) || numeric <= 0) {
            return DEFAULT_FONT_SIZE;
        }
        return clampNumber(Math.round(numeric), FONT_SIZE_LIMITS.min, FONT_SIZE_LIMITS.max);
    }

    function normalizeBlock(block) {
        const position = block.position || {};
        const id = block.id || generateClientId();
        const type = typeof block.type === 'string' && block.type.trim() ? block.type : 'text';
        const typography = (block.typography && typeof block.typography === 'object')
            ? { ...block.typography }
            : {};
        typography.fontFamily = sanitizeFontValue(typography.fontFamily);
        if (type !== 'image') {
            typography.fontSize = normalizeFontSizeValue(typography.fontSize ?? DEFAULT_FONT_SIZE);
        } else if (typography.fontSize != null) {
            typography.fontSize = normalizeFontSizeValue(typography.fontSize);
        }
        const marginSource = block.margin ?? block.padding ?? null;
        const margin = normalizeMargin(marginSource, type);
        return {
            id,
            type,
            content: block.content ?? '',
            backgroundColor: block.backgroundColor ?? '#ffffff',
            textColor: block.textColor ?? '#1c2333',
            borderRadius: typeof block.borderRadius === 'number' ? block.borderRadius : 12,
            imageUrl: block.imageUrl || null,
            typography,
            margin,
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
        if (!container.dataset.pageMenuBound) {
            container.addEventListener('contextmenu', (event) => {
                const thumb = event.target.closest('.page-thumb');
                if (!thumb) return;
                event.preventDefault();
                event.stopPropagation();
                const pageId = thumb.dataset.pageId;
                const anchor = thumb.querySelector('.page-thumb__menu') || thumb;
                openPageMenu(event, pageId, anchor);
            });
            container.dataset.pageMenuBound = 'true';
        }
        container.appendChild(createPageInsertButton(0));
        state.pages.forEach((page, index) => {
            container.appendChild(createPagePreview(page));
            container.appendChild(createPageInsertButton(index + 1));
        });
    }

    function openPageMenu(event, pageId, anchorElement = null) {
        if (!state.pageMenu.element) return;
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }
        const menu = state.pageMenu.element;
        state.pageMenu.pageId = pageId;
        state.pageMenu.open = true;
        state.pageMenu.anchor = anchorElement || (event?.currentTarget && event.currentTarget.nodeType === 1 ? event.currentTarget : null);
        menu.hidden = false;
        menu.style.visibility = 'hidden';
        positionPageMenuForEvent(menu, event, anchorElement);
        menu.style.visibility = '';
        const firstItem = menu.querySelector('.page-menu__item');
        if (firstItem) {
            firstItem.focus({ preventScroll: true });
        }
    }

    function closePageMenu() {
        if (!state.pageMenu.element) return;
        state.pageMenu.open = false;
        state.pageMenu.pageId = null;
        state.pageMenu.anchor = null;
        state.pageMenu.element.hidden = true;
    }

    function handlePageMenuAction(actionId) {
        const pageId = state.pageMenu.pageId;
        closePageMenu();
        if (!pageId) return;
        switch (actionId) {
            case 'rename':
                renamePage(pageId);
                break;
            case 'duplicate':
                duplicatePage(pageId);
                break;
            case 'copy':
                copyPageToClipboard(pageId);
                break;
            case 'delete':
                deletePageById(pageId);
                break;
            default:
                break;
        }
    }

    function positionPageMenuForEvent(menu, event, anchorElement) {
        const anchorRect = anchorElement?.getBoundingClientRect?.();
        const width = menu.offsetWidth || 200;
        const height = menu.offsetHeight || 150;
        const margin = 10;
        let left = event?.clientX ?? window.innerWidth / 2;
        let top = event?.clientY ?? window.innerHeight / 2;
        if (anchorRect) {
            left = anchorRect.right - width;
            top = anchorRect.bottom + 6;
        }
        if (left + width + margin > window.innerWidth) {
            left = Math.max(margin, window.innerWidth - width - margin);
        }
        if (top + height + margin > window.innerHeight) {
            top = Math.max(margin, window.innerHeight - height - margin);
        }
        menu.style.left = `${Math.round(left)}px`;
        menu.style.top = `${Math.round(top)}px`;
    }

    function renamePage(pageId) {
        const page = state.pages.find((item) => item.id === pageId);
        if (!page) return;
        const value = prompt('Rename page', page.name || `Page ${page.order + 1}`);
        if (value === null) return;
        const nextName = value.trim() || `Page ${page.order + 1}`;
        syncActivePageBlocks();
        page.name = nextName;
        state.layout.pages = state.pages;
        renderPagesSidebar();
        queueLayoutSync();
        showToast(`Renamed to ${nextName}`);
    }

    function duplicatePage(pageId) {
        const index = state.pages.findIndex((item) => item.id === pageId);
        if (index === -1) return;
        syncActivePageBlocks();
        const source = state.pages[index];
        const clonedBlocks = (source.blocks || []).map((block) => cloneBlockForPage(block));
        const nextName = `${source.name || 'Page'} copy`;
        const newPage = {
            ...source,
            id: generatePageId(),
            name: nextName,
            blocks: clonedBlocks,
        };
        state.pages.splice(index + 1, 0, newPage);
        resortPages();
        state.layout.pages = state.pages;
        setActivePage(newPage.id, { force: true, skipPersist: true });
        queueLayoutSync();
        showToast('Page duplicated');
    }

    async function copyPageToClipboard(pageId) {
        const page = state.pages.find((item) => item.id === pageId);
        if (!page) return;
        syncActivePageBlocks();
        const payload = {
            ...page,
            blocks: (page.blocks || []).map((block) => ({
                ...block,
                position: block.position ? { ...block.position } : undefined,
                margin: block.margin ? { ...block.margin } : undefined,
                typography: block.typography ? { ...block.typography } : undefined,
            })),
        };
        const text = JSON.stringify(payload, null, 2);
        try {
            if (navigator.clipboard?.writeText) {
                await navigator.clipboard.writeText(text);
                showToast('Page copied to clipboard');
                return;
            }
        } catch (error) {
            console.warn('Clipboard write failed', error);
        }
        const temp = document.createElement('textarea');
        temp.value = text;
        document.body.appendChild(temp);
        temp.select();
        try {
            document.execCommand('copy');
            showToast('Page copied to clipboard');
        } catch (error) {
            console.warn('Fallback clipboard copy failed', error);
            showToast('Unable to copy page', true);
        } finally {
            temp.remove();
        }
    }

    function deletePageById(pageId) {
        const page = state.pages.find((item) => item.id === pageId);
        if (!page) return;
        const confirmed = confirm(`Delete "${page.name || 'this page'}"? This cannot be undone.`);
        if (!confirmed) return;
        syncActivePageBlocks();
        hydratedPages.delete(pageId);
        state.pages = state.pages.filter((item) => item.id !== pageId);
        resortPages();
        const nowActive = state.activePageId === pageId;
        if (nowActive) {
            const fallback = state.pages[0] || null;
            state.activePageId = fallback ? fallback.id : null;
            state.layout.activePageId = state.activePageId;
        }
        state.layout.pages = state.pages;
        if (state.activePageId) {
            setActivePage(state.activePageId, { force: true, skipPersist: true });
        } else {
            state.layout.activePageId = null;
            state.layout.blocks = [];
            state.blocks.clear();
            state.blockElements.forEach((el) => el.remove());
            state.blockElements.clear();
            state.blockOrder = [];
            if (els.canvas) {
                els.canvas.innerHTML = '';
            }
            renderPagesSidebar();
        }
        queueLayoutSync();
        showToast('Page deleted');
    }

    function cloneBlockForPage(block) {
        const position = block.position ? { ...block.position } : {};
        const margin = block.margin ? { ...block.margin } : null;
        const typography = block.typography ? { ...block.typography } : null;
        return {
            ...block,
            id: generateClientId(),
            position,
            margin,
            typography,
        };
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
        const button = document.createElement('div');
        button.className = 'page-thumb';
        button.setAttribute('role', 'button');
        button.tabIndex = 0;
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
        const actions = document.createElement('div');
        actions.className = 'page-thumb__actions';
        const menuTrigger = document.createElement('button');
        menuTrigger.type = 'button';
        menuTrigger.className = 'page-thumb__menu';
        menuTrigger.setAttribute('aria-label', 'Page actions');
        menuTrigger.innerHTML = '&#8942;';
        const openMenu = (event) => openPageMenu(event, page.id, menuTrigger);
        menuTrigger.addEventListener('click', openMenu);
        menuTrigger.addEventListener('contextmenu', (event) => {
            event.preventDefault();
            openMenu(event);
        });
        menuTrigger.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                openMenu(event);
            }
        });
        actions.appendChild(menuTrigger);
        preview.appendChild(actions);

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
        button.addEventListener('click', () => setActivePage(page.id));
        button.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                setActivePage(page.id);
            }
        });
        button.addEventListener('contextmenu', (event) => {
            event.preventDefault();
            const anchor = button.querySelector('.page-thumb__menu') || button;
            openPageMenu(event, page.id, anchor);
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
                typography: { fontFamily: DEFAULT_FONT_VALUE, fontSize: DEFAULT_FONT_SIZE },
                margin: defaultMarginForType(type),
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
        applyBlockSpacing(block, element);
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

    function applyBlockSpacing(block, element = state.blockElements.get(block.id)) {
        if (!element) return;
        const wrapper = element.querySelector('.block__content-wrapper');
        if (!wrapper) return;
        const margin = ensureBlockMargin(block);
        wrapper.style.paddingTop = `${margin.top}px`;
        wrapper.style.paddingRight = `${margin.right}px`;
        wrapper.style.paddingBottom = `${margin.bottom}px`;
        wrapper.style.paddingLeft = `${margin.left}px`;
    }

    function applyBlockTypography(block, element = state.blockElements.get(block.id)) {
        if (!element || block.type === 'image') return;
        const contentEl = element.querySelector('.block__content');
        if (!contentEl) return;
        const fontOption = getFontOption(block.typography?.fontFamily);
        contentEl.style.fontFamily = fontOption.css;
        const fontSize = normalizeFontSizeValue(block.typography?.fontSize ?? DEFAULT_FONT_SIZE);
        block.typography = { ...(block.typography || {}), fontSize };
        contentEl.style.fontSize = `${fontSize}px`;
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
        if (els.inspectorFontSize) {
            const sizeValue = normalizeFontSizeValue(block.typography?.fontSize ?? DEFAULT_FONT_SIZE);
            block.typography = { ...(block.typography || {}), fontSize: sizeValue };
            els.inspectorFontSize.value = sizeValue;
            els.inspectorFontSize.disabled = isImage;
            const fontSizeField = els.inspectorFontSize.closest('.field');
            if (fontSizeField) {
                fontSizeField.hidden = isImage;
            }
        }
        els.inspectorLeft.value = block.position.left;
        els.inspectorTop.value = block.position.top;
        els.inspectorWidth.value = block.position.width;
        els.inspectorHeight.value = block.position.height;
        els.inspectorBg.value = toHexColor(block.backgroundColor ?? '#ffffff');
        els.inspectorFg.value = toHexColor(block.textColor ?? '#1c2333');
        els.inspectorRadius.value = block.borderRadius ?? 12;
        const margin = ensureBlockMargin(block);
        if (els.inspectorMarginTop) els.inspectorMarginTop.value = margin.top;
        if (els.inspectorMarginRight) els.inspectorMarginRight.value = margin.right;
        if (els.inspectorMarginBottom) els.inspectorMarginBottom.value = margin.bottom;
        if (els.inspectorMarginLeft) els.inspectorMarginLeft.value = margin.left;
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

    function applyAgentOptionsFromServer(options) {
        if (!options || typeof options !== 'object') return;
        updateAgentPermissionsUI();
    }

    function initChatInterface() {
        if (!els.chatLauncher || !els.chatPanel) return;
        if (!state.chat.messages.length) {
            pushChatMessage({
                role: 'assistant',
                content: 'Summon the spotlight to plan your layout. I will show every agent step before placing any content.',
            });
        }
        els.chatLauncher.addEventListener('click', () => toggleChatPanel(!state.chat.open));
        if (els.chatClose) {
            els.chatClose.addEventListener('click', () => toggleChatPanel(false));
        }
        if (els.chatBackdrop) {
            els.chatBackdrop.addEventListener('click', () => toggleChatPanel(false));
        }
        document.addEventListener('keydown', (event) => {
            const key = typeof event.key === 'string' ? event.key.toLowerCase() : '';
            if ((event.metaKey || event.ctrlKey) && key === 'k') {
                event.preventDefault();
                toggleChatPanel(true);
                if (els.chatInput) {
                    els.chatInput.focus();
                    els.chatInput.select();
                }
                return;
            }
            if (key === 'escape' && state.chat.open) {
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
        if (els.chatAgentAllowEdits) {
            els.chatAgentAllowEdits.addEventListener('change', handleAgentPermissionToggle);
        }
        if (els.chatAgentAllowWeb) {
            els.chatAgentAllowWeb.addEventListener('change', handleAgentWebToggle);
        }
        if (els.chatAgentOptionsToggle) {
            els.chatAgentOptionsToggle.addEventListener('click', () => toggleAgentOptionsPanel());
        }
        if (els.chatAgentViewMode) {
            els.chatAgentViewMode.addEventListener('change', handleAgentViewModeChange);
        }
        setChatStatus('Assistant ready');
        updateAgentToggle();
        renderSpotlightProgress();
    }

    function toggleChatPanel(forceOpen) {
        if (!els.chatPanel || !els.chatLauncher) return;
        const open = typeof forceOpen === 'boolean' ? forceOpen : !state.chat.open;
        state.chat.open = open;
        els.chatPanel.classList.toggle('chat-panel--open', open);
        els.chatPanel.setAttribute('aria-hidden', open ? 'false' : 'true');
        els.chatLauncher.setAttribute('aria-expanded', open ? 'true' : 'false');
        if (els.chatBackdrop) {
            els.chatBackdrop.classList.toggle('is-visible', open);
            els.chatBackdrop.setAttribute('aria-hidden', open ? 'false' : 'true');
        }
        document.body.classList.toggle('is-chat-open', open);
        if (open) {
            applySavedChatPanelSize();
            renderChatMessages();
            renderSpotlightProgress();
            renderDesignIntent();
            scrollChatLogToBottom();
            if (els.chatInput) {
                els.chatInput.focus();
            }
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
        setChatProgressBar({ active: true, label: 'Planning steps…', indeterminate: true });
        const progressToken = state.chat.agentEnabled ? generateProgressToken() : null;
        if (progressToken) {
            startAgentProgressWatcher(progressToken);
        }
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
                    agentPermissions: {
                        allowLayoutEdits: !!state.chat.agentCanEdit,
                        allowWebSearch: !!state.chat.agentAllowWeb,
                    },
                    agentViewMode: state.chat.agentViewMode,
                    progressToken,
                }),
            });
            if (!response.ok) {
                throw new Error((await safeReadText(response)) || 'Assistant request failed.');
            }
            const data = await response.json();
            applyAgentOptionsFromServer(data.agentOptions);
            const replyAttachments = [];
            if (data.agentSnapshot) {
                state.chat.agentSnapshot = data.agentSnapshot;
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
            setChatProgressBar({ active: true, label: 'Applying changes…', percent: 90 });
            const traceSummary = formatAgentTraceSummary(data.agentTrace);
            if (traceSummary) {
                pushChatMessage({
                    role: 'system',
                    content: traceSummary,
                    variant: 'muted',
                });
            }
            if (data.actions?.layoutUpdated) {
                const previousLayout = cloneLayout(state.layout);
                await loadLayout(state.project);
                if (previousLayout && state.layout) {
                    const highlightPlan = diffLayouts(previousLayout, state.layout);
                    queueAgentHighlights(highlightPlan);
                }
                showToast('Agent updated layout.json');
            }
            if (data.tokenStats) {
                updateTokenStats(data.tokenStats);
            }
            if (progressToken || data.progressToken) {
                await finalizeAgentProgressWatcher(data.progressToken || progressToken);
            }
            setChatStatus('Assistant ready');
            setChatProgressBar({ active: false });
        } catch (error) {
            console.error(error);
            pushChatMessage({
                role: 'system',
                content: error.message || 'Unable to reach the assistant.',
            });
            showToast(error.message || 'Assistant unavailable', true);
            setChatStatus('Assistant unavailable');
            setChatProgressBar({ active: false });
            stopAgentProgressWatcher('Assistant unavailable.');
        } finally {
            state.chat.sending = false;
        }
    }

    function formatAgentTraceSummary(traceItems) {
        if (!Array.isArray(traceItems) || !traceItems.length) return '';
        const lines = [];
        const items = traceItems.slice(0, CHAT_TRACE_STEP_LIMIT);
        items.forEach((entry, idx) => {
            if (!entry || typeof entry !== 'object') return;
            const kind = (entry.kind || '').toString().toLowerCase();
            const iter = entry.iteration ? ` [iter ${entry.iteration}]` : '';
            let detail = summarizeTextSnippet(entry.message || entry.result || '');
            if (kind === 'tool') {
                const status = entry.status === 'error' ? '✖ error' : '✓ ok';
                const name = entry.name || 'tool';
                detail = `${status} · ${name}${detail ? ` — ${detail}` : ''}`;
            } else if (kind === 'limit' || kind === 'error') {
                detail = `⚠ ${detail || 'Agent stopped before finishing.'}`;
            } else if (!detail) {
                detail = kind || 'step';
            }
            lines.push(`${idx + 1}.${iter ? iter : ''} [${kind || 'step'}] ${detail}`);
        });
        const truncated = traceItems.length > CHAT_TRACE_STEP_LIMIT;
        if (truncated) {
            lines.push(`…${traceItems.length - CHAT_TRACE_STEP_LIMIT} more step(s) not shown…`);
        }
        return `Agent steps:\n${lines.join('\n')}`;
    }

    function summarizeTextSnippet(text, limit = CHAT_TRACE_TEXT_LIMIT) {
        if (!text) return '';
        const value = String(text).replace(/\s+/g, ' ').trim();
        if (!value) return '';
        if (value.length <= limit) return value;
        return `${value.slice(0, limit)}…`;
    }

    function pushChatMessage(message) {
        const payload = {
            id: `msg-${Date.now()}-${Math.random().toString(16).slice(2)}`,
            role: message.role || 'assistant',
            content: message.content || '',
            attachments: (message.attachments || []).map((att) => ({ ...att })),
            variant: message.variant || null,
        };
        state.chat.messages.push(payload);
        if (state.chat.messages.length > 200) {
            state.chat.messages = state.chat.messages.slice(-200);
        }
        renderChatMessages();
        return payload;
    }

    function cloneLayout(layout) {
        if (!layout) return null;
        try {
            return structuredClone(layout);
        } catch (error) {
            return JSON.parse(JSON.stringify(layout));
        }
    }

    function diffLayouts(previous, next) {
        if (!previous || !next) return [];
        const prevPages = new Map();
        const nextPages = new Map();
        getPagesFromLayout(previous).forEach((page) => {
            if (page && page.id) {
                prevPages.set(page.id, page);
            }
        });
        getPagesFromLayout(next).forEach((page) => {
            if (page && page.id) {
                nextPages.set(page.id, page);
            }
        });
        const changes = [];
        nextPages.forEach((page, pageId) => {
            const prevPage = prevPages.get(pageId);
            const changedBlocks = diffPageBlocks(prevPage, page);
            if (changedBlocks.length) {
                changes.push({ pageId, blockIds: changedBlocks });
            }
        });
        return changes;
    }

    function diffPageBlocks(prevPage, nextPage) {
        const changed = [];
        const prevBlocks = Array.isArray(prevPage?.blocks) ? prevPage.blocks : [];
        const nextBlocks = Array.isArray(nextPage?.blocks) ? nextPage.blocks : [];
        const prevMap = new Map(prevBlocks.map((block) => [block?.id, block]));
        nextBlocks.forEach((block) => {
            if (!block?.id) return;
            const prev = prevMap.get(block.id);
            if (!prev) {
                changed.push(block.id);
                return;
            }
            if (!blocksEquivalent(prev, block)) {
                changed.push(block.id);
            }
        });
        return changed;
    }

    function blocksEquivalent(a, b) {
        const keys = [
            'type',
            'content',
            'backgroundColor',
            'textColor',
            'borderRadius',
            'imageUrl',
        ];
        for (const key of keys) {
            if ((a?.[key] || null) !== (b?.[key] || null)) {
                return false;
            }
        }
        const posKeys = ['left', 'top', 'width', 'height'];
        for (const key of posKeys) {
            if ((a?.position?.[key] || 0) !== (b?.position?.[key] || 0)) {
                return false;
            }
        }
        if (!shallowEqual(a?.typography, b?.typography)) return false;
        if (!shallowEqual(a?.margin, b?.margin)) return false;
        return true;
    }

    function shallowEqual(a, b) {
        if (a === b) return true;
        if (!a || !b) return false;
        const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
        for (const key of keys) {
            if (a[key] !== b[key]) return false;
        }
        return true;
    }

    function getPagesFromLayout(layout) {
        if (!layout) return [];
        const pages = Array.isArray(layout.pages) && layout.pages.length ? layout.pages : null;
        if (pages) return pages;
        if (Array.isArray(layout.blocks) && layout.blocks.length) {
            return [
                {
                    id: layout.activePageId || 'page-1',
                    name: layout.activePageId || 'Page 1',
                    order: 0,
                    blocks: layout.blocks,
                },
            ];
        }
        return [];
    }

    function queueAgentHighlights(changes) {
        if (!Array.isArray(changes) || !changes.length) return;
        state.agentHighlightQueue.push(...changes);
        processAgentHighlightQueue();
    }

    async function processAgentHighlightQueue() {
        if (state.agentHighlightActive) return;
        const nextHighlight = state.agentHighlightQueue.shift();
        if (!nextHighlight) return;
        state.agentHighlightActive = true;
        try {
            await ensurePageActive(nextHighlight.pageId);
            await waitForBlockElements(nextHighlight.blockIds);
            await focusBlocksOnCanvas(nextHighlight.blockIds);
            flashBlocks(nextHighlight.blockIds);
        } finally {
            state.agentHighlightActive = false;
            if (state.agentHighlightQueue.length) {
                setTimeout(processAgentHighlightQueue, 200);
            }
        }
    }

    async function ensurePageActive(pageId) {
        if (!pageId || pageId === state.activePageId) return;
        const targetPage = state.pages.find((page) => page.id === pageId);
        if (!targetPage) return;
        setActivePage(pageId, { force: true });
        await waitForAnimationFrame();
        await waitForAnimationFrame();
    }

    function waitForBlockElements(blockIds, maxAttempts = 8) {
        return new Promise((resolve) => {
            let attempts = 0;
            const check = () => {
                const missing = blockIds.some((id) => !state.blockElements.get(id));
                if (!missing || attempts >= maxAttempts) {
                    resolve();
                    return;
                }
                attempts += 1;
                requestAnimationFrame(check);
            };
            check();
        });
    }

    async function focusBlocksOnCanvas(blockIds) {
        if (!Array.isArray(blockIds) || !blockIds.length) return;
        const blocks = blockIds
            .map((id) => state.blocks.get(id))
            .filter(Boolean);
        if (!blocks.length) return;
        fitBlocksToViewport(blocks);
        await waitForAnimationFrame();
        const panel = els.canvasPanel;
        if (!panel) return;
        const panelRect = panel.getBoundingClientRect();
        const blockRects = blockIds
            .map((id) => state.blockElements.get(id))
            .filter(Boolean)
            .map((el) => el.getBoundingClientRect());
        if (!blockRects.length) return;
        const minLeft = Math.min(...blockRects.map((rect) => rect.left));
        const maxRight = Math.max(...blockRects.map((rect) => rect.right));
        const minTop = Math.min(...blockRects.map((rect) => rect.top));
        const maxBottom = Math.max(...blockRects.map((rect) => rect.bottom));
        const targetCenterX = (minLeft + maxRight) / 2;
        const targetCenterY = (minTop + maxBottom) / 2;
        const deltaX = targetCenterX - (panelRect.left + panelRect.width / 2);
        const deltaY = targetCenterY - (panelRect.top + panelRect.height / 2);
        panel.scrollBy({ left: deltaX, top: deltaY, behavior: 'smooth' });
    }

    function fitBlocksToViewport(blocks) {
        const panel = els.canvasPanel;
        if (!panel) return;
        const dims = state.layout?.dimensions || { width: 794, height: 1123 };
        let minLeft = Infinity;
        let minTop = Infinity;
        let maxRight = -Infinity;
        let maxBottom = -Infinity;
        blocks.forEach((block) => {
            const pos = block.position || {};
            const left = pos.left ?? 0;
            const top = pos.top ?? 0;
            const width = pos.width ?? 0;
            const height = pos.height ?? 0;
            minLeft = Math.min(minLeft, left);
            minTop = Math.min(minTop, top);
            maxRight = Math.max(maxRight, left + width);
            maxBottom = Math.max(maxBottom, top + height);
        });
        if (!Number.isFinite(minLeft) || !Number.isFinite(minTop)) return;
        const margin = 40;
        const targetWidth = Math.min(maxRight - minLeft + margin * 2, dims.width);
        const targetHeight = Math.min(maxBottom - minTop + margin * 2, dims.height);
        const availableWidth = Math.max(panel.clientWidth - 80, 120);
        const availableHeight = Math.max(panel.clientHeight - 80, 120);
        if (availableWidth <= 0 || availableHeight <= 0) return;
        const zoomForWidth = availableWidth / targetWidth;
        const zoomForHeight = availableHeight / targetHeight;
        const desiredZoom = clampNumber(Math.min(zoomForWidth, zoomForHeight), ZOOM_CONFIG.min, ZOOM_CONFIG.max);
        if (Math.abs(desiredZoom - state.zoom) > 0.05) {
            setCanvasZoom(desiredZoom);
        }
    }

    function flashBlocks(blockIds) {
        blockIds.forEach((id) => {
            const element = state.blockElements.get(id);
            if (!element) return;
            element.classList.add('block--agent-flash');
            setTimeout(() => {
                element.classList.remove('block--agent-flash');
            }, 1100);
        });
    }

    function waitForAnimationFrame() {
        return new Promise((resolve) => requestAnimationFrame(() => resolve()));
    }

    function parseMarkdown(text) {
        // Convert markdown to HTML
        if (!text) return '';

        // HTML-escape the content to prevent XSS, but we'll unescape it for safe markdown elements
        const escapeHtml = (unsafe) => {
            return unsafe
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        };

        // First, extract code blocks to preserve them during other transformations
        const codeBlocks = [];
        text = text.replace(/```([\s\S]*?)```/g, (match, code) => {
            const index = codeBlocks.length;
            codeBlocks[index] = `<pre class="chat-md-code"><code>${escapeHtml(code)}</code></pre>`;
            return `{{CODE_BLOCK_${index}}}`;
        });

        // Then extract inline code to preserve it
        const inlineCodes = [];
        text = text.replace(/`([^`]+)`/g, (match, code) => {
            const index = inlineCodes.length;
            inlineCodes[index] = `<code class="chat-md-inline">${escapeHtml(code)}</code>`;
            return `{{INLINE_CODE_${index}}}`;
        });

        // Convert headers
        text = text.replace(/^### (.*$)/gm, '<h3>$1</h3>');
        text = text.replace(/^## (.*$)/gm, '<h2>$1</h2>');
        text = text.replace(/^# (.*$)/gm, '<h1>$1</h1>');

        // Convert bold and italic (after headers)
        text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');

        // Convert links
        text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');

        // Convert bullet points
        text = text.replace(/^\s*\*\s(.*)$/gm, '<li>$1</li>');
        text = text.replace(/(<li>.*<\/li>[\s\n]*)+/g, '<ul class="chat-md-list">$&</ul>');

        // Convert numbered lists
        text = text.replace(/^\s*\d+\.\s(.*)$/gm, '<li>$1</li>');
        text = text.replace(/(<li>.*<\/li>[\s\n]*)+/g, '<ol class="chat-md-list">$&</ol>');

        // Convert paragraphs (split by double newline)
        text = text.replace(/\n\s*\n/g, '</p>\n<p>');

        // Replace single line breaks with <br> (inside paragraphs)
        text = text.replace(/([^\n])\n([^\n])/g, '$1<br>$2');

        // Restore code blocks
        text = text.replace(/\{\{CODE_BLOCK_(\d+)\}\}/g, (match, index) => codeBlocks[parseInt(index)]);
        text = text.replace(/\{\{INLINE_CODE_(\d+)\}\}/g, (match, index) => inlineCodes[parseInt(index)]);

        // Wrap in paragraph tags if needed (not already wrapped)
        if (text && !text.trim().startsWith('<')) {
            text = '<p>' + text + '</p>';
        }

        return text;
    }

    function renderChatMessages() {
        if (!els.chatLog) return;
        els.chatLog.innerHTML = '';
        state.chat.messages.forEach((message) => {
            const wrapper = document.createElement('div');
            wrapper.className = `chat-message chat-message--${message.role}`;
            if (message.variant) {
                wrapper.classList.add(`chat-message--${message.variant}`);
            }
            const bubble = document.createElement('div');
            bubble.className = 'chat-message__bubble';
            const meta = document.createElement('div');
            meta.className = 'chat-message__meta';
            const roleLabel =
                message.role === 'user' ? 'You' : message.role === 'assistant' ? 'Fyona' : 'System';
            meta.textContent = roleLabel;
            bubble.appendChild(meta);
            const textEl = document.createElement('div');
            textEl.className = 'chat-message__text';
            textEl.innerHTML = parseMarkdown(message.content || '');
            if (message.variant === 'muted') {
                textEl.classList.add('chat-message__text--muted');
            }
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

    function setChatProgressBar(options = {}) {
        const bar = els.chatProgressbar;
        const fill = els.chatProgressbarFill;
        const label = els.chatProgressbarLabel;
        if (!bar || !fill || !label) return;
        const active = !!options.active;
        if (!active) {
            bar.hidden = true;
            bar.classList.remove('is-indeterminate');
            fill.style.width = '0%';
            label.textContent = '';
            return;
        }
        const percent = typeof options.percent === 'number' ? clampNumber(options.percent, 0, 100) : null;
        const indeterminate = !!options.indeterminate;
        bar.hidden = false;
        bar.classList.toggle('is-indeterminate', indeterminate);
        label.textContent = options.label || 'Working…';
        if (indeterminate) {
            fill.style.width = '40%';
        } else if (percent === null) {
            fill.style.width = '0%';
        } else {
            fill.style.width = `${percent}%`;
        }
    }

    function generateProgressToken() {
        return `progress-${Date.now().toString(16)}-${Math.random().toString(16).slice(2, 10)}`;
    }

    function startAgentProgressWatcher(progressId) {
        if (!progressId) return;
        stopAgentProgressWatcher();
        toggleChatPanel(true);
        setChatProgressBar({ active: true, label: 'Agent running…', indeterminate: true });
        const message = pushChatMessage({
            role: 'system',
            content: 'Agent preparing tasks…',
            variant: 'muted',
        });
        state.chat.progress = {
            id: progressId,
            timer: null,
            messageId: message.id,
            lastStatus: message.content,
            historyLength: 0,
            events: [],
        };
        renderSpotlightProgress();
        pollAgentProgress();
        state.chat.progress.timer = window.setInterval(() => {
            pollAgentProgress();
        }, 2000);
    }

    function stopAgentProgressWatcher(finalText) {
        const watcher = state.chat.progress;
        if (watcher.timer) {
            clearInterval(watcher.timer);
        }
        if (finalText && watcher.messageId) {
            updateAgentProgressMessage(finalText, true);
        }
        setChatProgressBar({ active: false });
        const retainedEvents = Array.isArray(watcher.events) ? watcher.events.slice() : [];
        const retainedStatus = watcher.lastStatus;
        state.chat.progress = {
            id: null,
            timer: null,
            messageId: null,
            lastStatus: retainedStatus,
            historyLength: 0,
            events: retainedEvents,
        };
        renderSpotlightProgress();
    }

    async function finalizeAgentProgressWatcher(progressId) {
        if (!progressId) {
            stopAgentProgressWatcher();
            return;
        }
        await pollAgentProgress({ overrideId: progressId });
        stopAgentProgressWatcher();
    }

    async function pollAgentProgress(options = {}) {
        const progressId = options.overrideId || state.chat.progress.id;
        if (!progressId) return null;
        try {
            const response = await fetch(`/api/chat/progress/${encodeURIComponent(progressId)}`);
            if (!response.ok) {
                throw new Error('progress unavailable');
            }
            const data = await response.json();
            if (!data.success || !data.progress) {
                throw new Error('progress unavailable');
            }
            const progress = data.progress;
            updateAgentProgressMessage(progress, !!progress.done);
            if (progress.done && state.chat.progress.id === progressId) {
                stopAgentProgressWatcher();
            }
            return progress;
        } catch (error) {
            console.warn('Progress polling failed:', error);
            updateAgentProgressMessage('Assistant progress unavailable.', true);
            stopAgentProgressWatcher();
            return null;
        }
    }

    function updateAgentProgressMessage(progress, finalize = false) {
        if (!progress) return;
        const watcher = state.chat.progress;
        const targetId = watcher.messageId;
        if (!targetId) return;
        const message = state.chat.messages.find((entry) => entry.id === targetId);
        if (!message) return;
        const text = typeof progress === 'string' ? progress : formatProgressLabel(progress);
        message.content = text;
        watcher.lastStatus = text;
        if (typeof progress === 'object' && Array.isArray(progress.events)) {
            watcher.historyLength = progress.events.length;
            watcher.events = progress.events.slice();
        }
        const percentGuess = Math.min(95, Math.max(10, (watcher.events.length || 1) * 12));
        const isDone = !!(progress && typeof progress === 'object' && progress.done);
        const isError = !!(progress && typeof progress === 'object' && progress.error);
        setChatProgressBar({
            active: true,
            label: watcher.lastStatus || 'Working…',
            percent: isDone ? 100 : percentGuess,
            indeterminate: isError,
        });
        renderChatMessages();
        renderSpotlightProgress(progress);
        if (finalize) {
            state.chat.progress.messageId = null;
            setTimeout(() => setChatProgressBar({ active: false }), 250);
        }
    }

    function formatProgressLabel(progress) {
        if (!progress) return 'Agent progress unavailable.';
        if (typeof progress === 'string') return progress;
        const events = Array.isArray(progress.events) ? progress.events : [];
        const lines = [];
        events.forEach((event, index) => {
            const label = event.detail || event.status || 'Working…';
            lines.push(`${index + 1}. ${label}`);
        });
        if (progress.error) {
            lines.push(`Agent error — ${progress.error}`);
        } else if (progress.done) {
            lines.push(`Agent complete — ${progress.detail || progress.status || 'Finished.'}`);
        } else if (!events.length) {
            lines.push(`Agent progress — ${progress.detail || progress.status || 'Working…'}`);
        }
        return lines.join('\n');
    }

    function renderSpotlightProgress(progress) {
        if (!els.chatProgress) return;
        const container = els.chatProgress;
        const events = Array.isArray(progress?.events)
            ? progress.events
            : Array.isArray(state.chat.progress.events)
                ? state.chat.progress.events
                : [];
        container.innerHTML = '';
        if (!events.length) {
            const placeholder = document.createElement('li');
            placeholder.className = 'spotlight-step';
            const index = document.createElement('span');
            index.className = 'spotlight-step__index';
            index.textContent = '—';
            const body = document.createElement('div');
            body.className = 'spotlight-step__body';
            const title = document.createElement('p');
            title.className = 'spotlight-step__title';
            title.textContent = state.chat.progress.lastStatus || 'Awaiting a prompt.';
            const meta = document.createElement('p');
            meta.className = 'spotlight-step__meta';
            meta.textContent = 'Ask Fyona for a layout and watch each step appear here.';
            body.appendChild(title);
            body.appendChild(meta);
            placeholder.appendChild(index);
            placeholder.appendChild(body);
            container.appendChild(placeholder);
            return;
        }

        const hasError = !!(progress && typeof progress === 'object' && progress.error);
        const isDone = !!(progress && typeof progress === 'object' && progress.done);
        events.forEach((entry, idx) => {
            const event = entry || {};
            const item = document.createElement('li');
            item.className = 'spotlight-step';
            if (!isDone && !hasError && idx === events.length - 1) {
                item.classList.add('spotlight-step--active');
            }
            if (hasError && idx === events.length - 1) {
                item.classList.add('spotlight-step--error');
            }
            const index = document.createElement('span');
            index.className = 'spotlight-step__index';
            index.textContent = String(idx + 1).padStart(2, '0');

            const body = document.createElement('div');
            body.className = 'spotlight-step__body';
            const title = document.createElement('p');
            title.className = 'spotlight-step__title';
            const detail =
                typeof event === 'string'
                    ? event
                    : event.detail || event.status || event.title || 'Working…';
            title.textContent = detail;
            const meta = document.createElement('p');
            meta.className = 'spotlight-step__meta';
            const metaParts = [];
            if (typeof event === 'object') {
                if (event.status && event.status !== detail) {
                    metaParts.push(event.status);
                }
                if (event.kind) {
                    metaParts.push(String(event.kind));
                }
                if (event.message) {
                    metaParts.push(String(event.message));
                }
            }
            if (hasError && idx === events.length - 1 && progress?.error) {
                metaParts.push(String(progress.error));
            }
            if (isDone && idx === events.length - 1) {
                metaParts.push('Complete');
            }
            meta.textContent = metaParts.filter(Boolean).join(' · ') || 'Agent step';
            body.appendChild(title);
            body.appendChild(meta);

            item.appendChild(index);
            item.appendChild(body);
            container.appendChild(item);
        });
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
            const details = document.createElement('details');
            details.className = 'chat-attachment__details';
            details.open = false;
            const summary = document.createElement('summary');
            summary.textContent = `Show ${attachment.label || attachment.type || 'attachment'}`;
            details.appendChild(summary);
            const pre = document.createElement('pre');
            pre.textContent = attachment.content;
            details.appendChild(pre);
            card.appendChild(details);
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
        setTerminalBusy(false);
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
            if (state.terminal.isBusy) return;
            const value = input.value.trim();
            if (!value) return;
            input.value = '';
            runTerminalCommand(value);
        });
        body.appendChild(promptForm);

        container.appendChild(header);
        container.appendChild(body);
        document.body.appendChild(container);
        container.addEventListener(
            'wheel',
            (event) => {
                if (!state.terminal.log) return;
                if (event.target && event.target.closest('.floating-terminal__log')) {
                    return;
                }
                if (event.target && event.target.closest('.floating-terminal__prompt input')) {
                    return;
                }
                state.terminal.log.scrollTop += event.deltaY;
                event.preventDefault();
            },
            { passive: false },
        );

        state.terminal.element = container;
        state.terminal.log = log;
        state.terminal.input = input;

        appendTerminalLine('Fyona terminal ready.', 'muted');
        appendTerminalLine('Type `help` to see available commands.', 'muted');
        return container;
    }

    function appendTerminalLine(text, variant = 'output') {
        if (!state.terminal.log) return;
        const shouldStick =
            Math.abs(
                state.terminal.log.scrollHeight -
                    (state.terminal.log.scrollTop + state.terminal.log.clientHeight),
            ) < 24;
        const line = document.createElement('div');
        line.className = `floating-terminal__line floating-terminal__line--${variant}`;
        line.textContent = text;
        state.terminal.log.appendChild(line);
        if (shouldStick) {
            state.terminal.log.scrollTop = state.terminal.log.scrollHeight;
        }
    }

    function setTerminalBusy(isBusy) {
        state.terminal.isBusy = isBusy;
        if (state.terminal.input) {
            state.terminal.input.disabled = isBusy;
            state.terminal.input.placeholder = isBusy ? 'Running…' : 'Type a command…';
        }
        if (state.terminal.element) {
            state.terminal.element.classList.toggle('floating-terminal--busy', isBusy);
        }
    }

    async function runTerminalCommand(command) {
        const trimmed = command.trim();
        if (!trimmed) return;
        if (state.terminal.isBusy) {
            appendTerminalLine('Terminal busy. Please wait for the current command to finish.', 'muted');
            return;
        }
        openFloatingTerminal();
        appendTerminalLine(`$ ${trimmed}`, 'input');
        setTerminalBusy(true);
        try {
            const response = await fetch('/api/terminal', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project: state.project, command: trimmed }),
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok || !data.success) {
                throw new Error(data.error || 'Unable to run command.');
            }
            appendTerminalLine(data.output || 'Done.', 'output');
            if (data.layoutUpdated) {
                await loadLayout(state.project);
            }
        } catch (error) {
            console.error(error);
            appendTerminalLine(error.message || 'Unable to run command.', 'error');
        } finally {
            setTerminalBusy(false);
        }
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

    function handleAgentPermissionToggle(event) {
        const checkbox = event.target;
        if (!checkbox) return;
        if (!state.chat.agentEnabled) {
            checkbox.checked = false;
            showToast('Enable Agent Mode before allowing edits.', true);
            return;
        }
        state.chat.agentCanEdit = !!checkbox.checked;
        updateAgentPermissionsUI();
        showToast(state.chat.agentCanEdit ? 'Agent can now edit layout.json.' : 'Agent edits disabled.');
    }

    function handleAgentWebToggle(event) {
        const checkbox = event.target;
        if (!checkbox) return;
        if (!state.chat.agentEnabled) {
            checkbox.checked = false;
            showToast('Enable Agent Mode before allowing web search.', true);
            return;
        }
        if (!state.chat.bingSearchAvailable) {
            checkbox.checked = false;
            showToast('Bing web search is not configured on this server.', true);
            return;
        }
        state.chat.agentAllowWeb = !!checkbox.checked;
        updateAgentPermissionsUI();
        showToast(state.chat.agentAllowWeb ? 'Agent can now research with Bing search.' : 'Bing search disabled for the agent.');
    }

    function handleAgentViewModeChange(event) {
        const select = event.target;
        if (!select) return;
        state.chat.agentViewMode = select.value;
        updateAgentPermissionsUI();
        showToast(`Agent view mode changed to ${select.value}.`);
    }

    function toggleAgentOptionsPanel(forceOpen) {
        if (!els.chatAgentOptionsToggle || !els.chatAgentIndicator) return;
        if (!state.chat.agentEnabled) {
            state.chat.optionsOpen = false;
            updateAgentPermissionsUI();
            return;
        }
        const next = typeof forceOpen === 'boolean' ? forceOpen : !state.chat.optionsOpen;
        state.chat.optionsOpen = next;
        updateAgentPermissionsUI();
    }

    function disableAgentMode({ silent = false } = {}) {
        const wasEnabled = state.chat.agentEnabled;
        state.chat.agentEnabled = false;
        state.chat.agentSnapshot = null;
        state.chat.agentCanEdit = false;
        state.chat.agentAllowWeb = false;
        state.chat.optionsOpen = false;
        updateAgentToggle();
        if (!silent && wasEnabled) {
            pushChatMessage({
                role: 'system',
                content: 'Agent Mode disabled. I will only use chat messages unless you re-enable it.',
            });
            updateChatProjectStatus();
        }
    }

    async function toggleAgentMode() {
        if (state.chat.agentEnabled) {
            disableAgentMode();
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
            const response = await fetch(`/api/chat/agent-snapshot?project=${encodeURIComponent(state.project)}&agentViewMode=${encodeURIComponent(state.chat.agentViewMode)}`);
            if (!response.ok) {
                throw new Error((await safeReadText(response)) || 'Unable to inspect project structure.');
            }
            const data = await response.json();
            state.chat.agentEnabled = true;
            state.chat.agentSnapshot = data.snapshot;
            state.chat.agentCanEdit = false;
            state.chat.agentAllowWeb = false;
            state.chat.optionsOpen = false;
            pushChatMessage({
                role: 'system',
                content: 'Agent Mode enabled. The assistant can now inspect the project directory and layout JSON. Enable “Allow layout edits” when you want the agent to run commands.',
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
            updateAgentPermissionsUI();
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
        updateAgentPermissionsUI();
    }

    function updateAgentPermissionsUI() {
        if (!state.chat.agentEnabled && state.chat.optionsOpen) {
            state.chat.optionsOpen = false;
        }
        if (els.chatAgentAllowEdits) {
            els.chatAgentAllowEdits.disabled = !state.chat.agentEnabled;
            els.chatAgentAllowEdits.checked = state.chat.agentEnabled && !!state.chat.agentCanEdit;
            const wrapper = els.chatAgentAllowEdits.closest('.chat-agent-permission');
            if (wrapper) {
                wrapper.classList.toggle('is-disabled', els.chatAgentAllowEdits.disabled);
            }
        }
        if (els.chatAgentAllowWeb) {
            const disabled = !state.chat.agentEnabled || !state.chat.bingSearchAvailable;
            els.chatAgentAllowWeb.disabled = disabled;
            els.chatAgentAllowWeb.checked = state.chat.agentEnabled && !!state.chat.agentAllowWeb;
            const wrapper = els.chatAgentAllowWeb.closest('.chat-agent-permission');
            if (wrapper) {
                wrapper.classList.toggle('is-disabled', disabled);
                if (disabled && !state.chat.bingSearchAvailable) {
                    wrapper.title = 'Bing web search is not configured on this server.';
                } else {
                    wrapper.removeAttribute('title');
                }
            }
        }
        if (els.chatAgentViewMode) {
            els.chatAgentViewMode.disabled = !state.chat.agentEnabled;
            els.chatAgentViewMode.value = state.chat.agentViewMode;
        }
        if (els.chatAgentOptionsToggle) {
            els.chatAgentOptionsToggle.disabled = !state.chat.agentEnabled;
            els.chatAgentOptionsToggle.setAttribute(
                'aria-expanded',
                state.chat.agentEnabled && state.chat.optionsOpen ? 'true' : 'false'
            );
        }
        if (els.chatAgentIndicator) {
            els.chatAgentIndicator.hidden = !(state.chat.agentEnabled && state.chat.optionsOpen);
        }
        if (els.chatAgentPermissionSummary) {
            let summary;
            if (!state.chat.agentEnabled) {
                summary = 'Enable Agent Mode to share project structure and layout.';
            } else if (state.chat.agentCanEdit && state.chat.agentAllowWeb) {
                summary = 'Fyona can edit layout.json and research via Bing web search.';
            } else if (state.chat.agentCanEdit) {
                summary = 'Fyona can now read files and run layout-editing commands.';
            } else if (state.chat.agentAllowWeb) {
                summary = 'Fyona can research with Bing search but cannot change files.';
            } else {
                summary = 'Fyona has read-only access until you allow layout edits.';
            }
            if (state.chat.agentEnabled) {
                summary = `${summary} · Fyona keeps issuing terminal commands and re-evaluating until the layout matches the request.`;
            }
            els.chatAgentPermissionSummary.textContent = summary;
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

    function renderDesignIntent() {
        if (!els.chatIntentCopy) return;
        const layout = state.layout;
        if (!layout) {
            els.chatIntentCopy.textContent = 'Fyona will sketch a plan once a project is loaded.';
            if (els.chatIntentPalette) {
                els.chatIntentPalette.innerHTML = '';
            }
            return;
        }
        const pieces = [];
        if (layout.format) {
            pieces.push(`${layout.format} ${layout.orientation || ''}`.trim());
        }
        if (layout.columns) {
            pieces.push(`${layout.columns}-column grid`);
        }
        if (layout.baseline) {
            pieces.push(`${layout.baseline}px baseline`);
        }
        if (layout.gutter) {
            pieces.push(`${layout.gutter}px gutters`);
        }
        const themeName = layout.theme?.name;
        const descriptor = themeName ? `“${themeName}”` : 'this spread';
        const layoutLine = pieces.filter(Boolean).join(' • ');
        const copyParts = [
            `Framing ${descriptor} with ${layoutLine || 'a grid-first pass'}.`,
            'Fyona will describe the visual intent before placing content.',
        ].filter(Boolean);
        els.chatIntentCopy.textContent = copyParts.join(' ');
        if (els.chatIntentPalette) {
            els.chatIntentPalette.innerHTML = '';
            const palette = layout.theme?.palette || {};
            Object.entries(palette).forEach(([key, value]) => {
                if (typeof value !== 'string' || !value.trim()) return;
                const swatch = document.createElement('span');
                swatch.className = 'spotlight-intent__swatch';
                swatch.style.background = value;
                swatch.title = `${key}: ${value}`;
                els.chatIntentPalette.appendChild(swatch);
            });
        }
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
