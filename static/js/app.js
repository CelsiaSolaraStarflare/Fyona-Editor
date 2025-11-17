document.addEventListener('DOMContentLoaded', () => {
    const els = {
        projectSelect: document.getElementById('project-select'),
        refreshProjects: document.getElementById('refresh-projects'),
        addText: document.getElementById('add-text'),
        addImage: document.getElementById('add-image'),
        saveLayout: document.getElementById('save-layout'),
        canvas: document.getElementById('canvas'),
        canvasWrapper: document.querySelector('.canvas-wrapper'),
        canvasPanel: document.querySelector('.canvas-panel'),
        inspectorEmpty: document.getElementById('inspector-empty'),
        inspectorForm: document.getElementById('inspector-form'),
        inspectorType: document.getElementById('inspector-type'),
        inspectorContent: document.getElementById('inspector-content'),
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
        agentToggle: document.getElementById('agent-toggle'),
        inspectorPanel: document.getElementById('inspector-panel'),
        agentConsole: document.getElementById('agent-console'),
        agentClose: document.getElementById('agent-close'),
        agentRun: document.getElementById('agent-run'),
        agentCancel: document.getElementById('agent-cancel'),
        agentPrompt: document.getElementById('agent-prompt'),
        agentHistory: document.getElementById('agent-history'),
        agentResponse: document.getElementById('agent-response'),
    };

    const state = {
        project: 'default',
        layout: null,
        blocks: new Map(),
        blockOrder: [],
        blockElements: new Map(),
        selectedId: null,
        activePointer: null,
        format: 'A4',
        orientation: 'portrait',
        pendingImageBlock: null,
        zoom: 1,
    };

    const agentState = {
        isOpen: false,
        running: false,
        abortController: null,
    };

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

    init();

    async function init() {
        configureZoomControl();
        bindUIEvents();
        window.addEventListener('resize', scheduleCanvasFit);
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

        bindAgentUI();
    }

    function bindAgentUI() {
        if (!els.agentToggle || !els.agentConsole) return;
        els.agentToggle.addEventListener('click', () => openAgentConsole());
        if (els.agentClose) {
            els.agentClose.addEventListener('click', () => closeAgentConsole());
        }
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && agentState.isOpen && !agentState.running) {
                closeAgentConsole();
            }
        });
        if (els.agentRun) {
            els.agentRun.addEventListener('click', () => runAgentWorkflow());
        }
        if (els.agentCancel) {
            els.agentCancel.addEventListener('click', () => cancelAgentRun());
        }
        if (els.agentPrompt && !els.agentPrompt.value) {
            els.agentPrompt.value = 'Study the current layout and refine hierarchy, spacing, and storytelling.';
        }
    }

    function openAgentConsole() {
        if (agentState.isOpen) return;
        agentState.isOpen = true;
        toggleAgentPalette(true);
        if (els.agentConsole?.hasAttribute('hidden')) {
            els.agentConsole.removeAttribute('hidden');
        }
        els.agentConsole?.setAttribute('aria-hidden', 'false');
        els.inspectorPanel?.classList.add('inspector--agent');
        if (els.agentResponse && !els.agentResponse.textContent) {
            els.agentResponse.textContent = 'Awaiting agent run…';
        }
        addAgentMessage({ role: 'system', text: 'Agent mode engaged. Share a brief and run the assistant.' });
        scheduleCanvasFit();
    }

    function closeAgentConsole(force = false) {
        if (!force && agentState.running) return;
        agentState.isOpen = false;
        toggleAgentPalette(false);
        els.inspectorPanel?.classList.remove('inspector--agent');
        if (els.agentConsole) {
            els.agentConsole.setAttribute('hidden', 'hidden');
            els.agentConsole.setAttribute('aria-hidden', 'true');
        }
        if (els.agentResponse) {
            els.agentResponse.textContent = '';
        }
        scheduleCanvasFit();
    }

    function toggleAgentPalette(enabled) {
        document.body.classList.toggle('agent-mode', enabled);
    }

    function setAgentRunning(isRunning) {
        agentState.running = isRunning;
        if (els.agentRun) {
            els.agentRun.disabled = isRunning;
            els.agentRun.textContent = isRunning ? 'Running…' : 'Run Agent';
        }
        if (els.agentCancel) {
            els.agentCancel.disabled = !isRunning;
        }
        if (!isRunning) {
            agentState.abortController = null;
        }
    }

    function addAgentMessage({
        role = 'system',
        text = '',
        snapshot = null,
        tone = 'info',
        reasoning = '',
        answer = '',
        events = [],
    } = {}) {
        if (!els.agentHistory) return;
        const stickToBottom = isAgentHistoryNearBottom();
        const entry = document.createElement('article');
        entry.className = `agent-history__entry agent-history__entry--${role}`;
        if (tone === 'error') {
            entry.classList.add('agent-history__entry--error');
        }
        const roleLabel = document.createElement('p');
        roleLabel.className = 'agent-history__role';
        roleLabel.textContent = role === 'assistant' ? 'Agent' : role === 'user' ? 'You' : 'System';
        entry.appendChild(roleLabel);

        if (role === 'system' && text) {
            const summaryTitle = tone === 'error' ? 'System alert' : 'System update';
            const details = createCollapsibleSection({
                summary: `${summaryTitle}: ${truncatePreview(text, 72)}`,
                bodyText: text,
                bodyClass: 'agent-history__text',
                defaultOpen: tone === 'error',
            });
            entry.appendChild(details);
        } else if (text) {
            const textEl = document.createElement('p');
            textEl.className = 'agent-history__text';
            textEl.textContent = text;
            entry.appendChild(textEl);
        }

        if (snapshot) {
            const img = document.createElement('img');
            img.className = 'agent-history__screenshot';
            img.alt = 'Canvas snapshot shared with agent';
            img.src = snapshot;
            entry.appendChild(img);
        }

        if (reasoning) {
            const reasoningDetails = createCollapsibleSection({
                summary: 'Reasoning trace',
                bodyText: reasoning,
                bodyClass: 'agent-history__reasoning',
            });
            entry.appendChild(reasoningDetails);
        }

        if (answer) {
            const answerEl = document.createElement('p');
            answerEl.className = 'agent-history__answer';
            answerEl.textContent = answer;
            entry.appendChild(answerEl);
        }

        if (Array.isArray(events) && events.length) {
            const list = document.createElement('ul');
            list.className = 'agent-history__events';
            events.forEach((event) => {
                const item = document.createElement('li');
                item.textContent = event.description || event.type || 'Agent action';
                list.appendChild(item);
            });
            entry.appendChild(list);
        }

        const meta = document.createElement('p');
        meta.className = 'agent-history__meta';
        meta.textContent = new Date().toLocaleTimeString();
        entry.appendChild(meta);

        els.agentHistory.appendChild(entry);
        if (stickToBottom) {
            scrollAgentHistoryToBottom();
        }

        if (role === 'assistant' && (answer || text) && els.agentResponse) {
            els.agentResponse.textContent = answer || text;
        }
    }

    async function runAgentWorkflow() {
        if (agentState.running) return;
        addAgentMessage({ role: 'system', text: 'Capturing canvas snapshot for the agent…' });
        setAgentRunning(true);
        if (els.agentResponse) {
            els.agentResponse.textContent = 'Agent is thinking…';
        }
        const promptText = (els.agentPrompt?.value || '').trim() || 'Review the layout and improve it for clarity.';
        let snapshot = null;
        try {
            snapshot = await captureCanvasSnapshot();
        } catch (error) {
            console.error(error);
            addAgentMessage({ role: 'system', text: error.message || 'Unable to capture snapshot.', tone: 'error' });
        }
        if (!snapshot) {
            addAgentMessage({ role: 'system', text: 'Snapshot capture unavailable, falling back to server rendering.', tone: 'error' });
            addAgentMessage({ role: 'user', text: promptText });
        } else {
            addAgentMessage({ role: 'user', text: promptText, snapshot });
        }

        const payload = {
            project: state.project,
            prompt: promptText,
            snapshot,
        };

        agentState.abortController = new AbortController();
        let response;
        try {
            response = await fetch('/api/agent/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
                signal: agentState.abortController.signal,
            });
        } catch (error) {
            if (error.name === 'AbortError') {
                addAgentMessage({ role: 'system', text: 'Agent run aborted.', tone: 'error' });
            } else {
                addAgentMessage({ role: 'system', text: error.message || 'Unable to reach agent endpoint.', tone: 'error' });
                showToast('Agent request failed', true);
            }
            setAgentRunning(false);
            return;
        }

        if (!response.ok) {
            const detail = await safeReadText(response);
            addAgentMessage({ role: 'system', text: detail || `Agent call failed (${response.status})`, tone: 'error' });
            showToast('Agent failed', true);
            setAgentRunning(false);
            return;
        }

        let data;
        try {
            data = await response.json();
        } catch (error) {
            addAgentMessage({ role: 'system', text: 'Unable to parse agent response.', tone: 'error' });
            setAgentRunning(false);
            return;
        }

        if (!data.success) {
            addAgentMessage({ role: 'system', text: data.error || 'Agent reported an error.', tone: 'error' });
            showToast('Agent error', true);
            setAgentRunning(false);
            return;
        }

        addAgentMessage({
            role: 'assistant',
            text: data.answer ? '' : 'Agent executed actions on the layout.',
            reasoning: data.reasoning || '',
            answer: data.answer || '',
            events: Array.isArray(data.events) ? data.events : [],
        });

        if (data.project && data.project !== state.project) {
            showToast(`Agent switched to project “${data.project}”`);
        }

        await loadLayout(data.project || state.project);
        addAgentMessage({ role: 'system', text: 'Canvas reloaded with agent changes.', tone: 'success' });
        showToast('Agent updated the canvas');

        setAgentRunning(false);
    }

    function cancelAgentRun() {
        if (!agentState.running || !agentState.abortController) return;
        agentState.abortController.abort();
        addAgentMessage({ role: 'system', text: 'Cancel requested.', tone: 'error' });
    }

    async function captureCanvasSnapshot() {
        if (typeof window.html2canvas !== 'function' || !els.canvas) {
            return null;
        }
        const options = {
            backgroundColor: '#ffffff',
            scale: Math.min(2, window.devicePixelRatio || 1.5),
            useCORS: true,
        };
        const canvas = await window.html2canvas(els.canvas, options);
        return canvas.toDataURL('image/png', 0.9);
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
        try {
            const response = await fetch(`/api/layout?project=${encodeURIComponent(project)}`);
            if (!response.ok) throw new Error('Failed to fetch layout');
            const layout = await response.json();

            state.project = project;
            state.layout = layout;
            state.blocks.clear();
            state.blockElements.forEach((el) => el.remove());
            state.blockElements.clear();
            state.blockOrder = [];

            (layout.blocks || []).forEach((block) => {
                state.blocks.set(block.id, normalizeBlock(block));
                state.blockOrder.push(block.id);
            });

            renderCanvas();
            deselectBlock();
            applyCanvasMeta(layout);
            updateCanvasSizeLabel();
        } catch (error) {
            console.error(error);
            showToast('Unable to load layout', true);
        }
    }

    function generateClientId() {
        return `block-${Math.random().toString(16).slice(2, 10)}`;
    }

    function normalizeBlock(block) {
        const position = block.position || {};
        const id = block.id || generateClientId();
        return {
            id,
            type: block.type || 'text',
            content: block.content ?? '',
            backgroundColor: block.backgroundColor ?? '#ffffff',
            textColor: block.textColor ?? '#1c2333',
            borderRadius: typeof block.borderRadius === 'number' ? block.borderRadius : 12,
            imageUrl: block.imageUrl || null,
            position: {
                left: Math.round(Number(position.left) || 0),
                top: Math.round(Number(position.top) || 0),
                width: Math.max(40, Math.round(Number(position.width) || 240)),
                height: Math.max(40, Math.round(Number(position.height) || 140)),
            },
        };
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
        const basePosition = {
            left: 120 + Math.floor(Math.random() * 60),
            top: 120 + Math.floor(Math.random() * 60),
            width: type === 'image' ? 260 : 260,
            height: type === 'image' ? 180 : 140,
        };

        const payload = {
            project: state.project,
            operation: 'add',
            block: {
                type,
                content: type === 'image' ? 'Double-click to add image' : 'Editable text',
                position: basePosition,
                backgroundColor: '#ffffff',
                textColor: '#1c2333',
                borderRadius: 12,
                imageUrl: null,
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

            const element = createBlockElement(block);
            els.canvas.appendChild(element);
            state.blockElements.set(block.id, element);
            selectBlock(block.id);
            showToast(`${type === 'image' ? 'Image' : 'Text'} block added`);
        } catch (error) {
            console.error(error);
            showToast('Unable to add block', true);
        }
    }

    async function deleteBlock(blockId) {
        try {
            const response = await fetch('/api/block', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    project: state.project,
                    operation: 'delete',
                    block_id: blockId,
                }),
            });
            if (!response.ok) throw new Error('Failed to delete block');

            const element = state.blockElements.get(blockId);
            if (element) element.remove();
            state.blockElements.delete(blockId);
            state.blocks.delete(blockId);
            state.blockOrder = state.blockOrder.filter((id) => id !== blockId);
            deselectBlock();
            showToast('Block deleted');
        } catch (error) {
            console.error(error);
            showToast('Unable to delete block', true);
        }
    }

    async function persistBlock(blockId, updates) {
        try {
            await fetch('/api/block', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    project: state.project,
                    operation: 'update',
                    block_id: blockId,
                    updates,
                }),
            });
        } catch (error) {
            console.error(error);
            showToast('Unable to sync block', true);
        }
    }

    async function saveCurrentLayout() {
        const layout = {
            ...state.layout,
            project: state.project,
            blocks: state.blockOrder
                .map((id) => state.blocks.get(id))
                .filter(Boolean)
                .map((block) => ({
                    ...block,
                    position: { ...block.position },
                })),
        };

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
    }

    function updateInspector(block) {
        if (!block) {
            els.inspectorForm.hidden = true;
            els.inspectorEmpty.hidden = false;
            if (els.imageOptions) {
                els.imageOptions.hidden = true;
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
        state.pendingImageBlock = blockId;
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
        const blockId = state.pendingImageBlock;
        state.pendingImageBlock = null;
        const block = state.blocks.get(blockId);
        if (!block) return;

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

    async function safeReadText(response) {
        try {
            return await response.text();
        } catch {
            return '';
        }
    }

    function createCollapsibleSection({ summary, bodyText, bodyClass, defaultOpen = false }) {
        const details = document.createElement('details');
        details.className = 'agent-history__details';
        if (defaultOpen) {
            details.setAttribute('open', 'open');
        }
        const summaryEl = document.createElement('summary');
        summaryEl.textContent = summary || 'Details';
        details.appendChild(summaryEl);
        if (bodyText) {
            const body = document.createElement('div');
            body.className = bodyClass || 'agent-history__text';
            body.textContent = bodyText;
            details.appendChild(body);
        }
        return details;
    }

    function truncatePreview(text, maxLength) {
        const clean = (text || '').trim();
        if (clean.length <= maxLength) return clean;
        return `${clean.slice(0, maxLength - 1)}…`;
    }

    function isAgentHistoryNearBottom() {
        if (!els.agentHistory) return false;
        const { scrollTop, scrollHeight, clientHeight } = els.agentHistory;
        return scrollHeight - (scrollTop + clientHeight) < 40;
    }

    function scrollAgentHistoryToBottom() {
        if (!els.agentHistory) return;
        els.agentHistory.scrollTo({ top: els.agentHistory.scrollHeight, behavior: 'smooth' });
    }
});
