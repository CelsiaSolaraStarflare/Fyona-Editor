document.addEventListener('DOMContentLoaded', () => {
    const els = {
        newProjectBtn: document.getElementById('new-project-btn'),
        modal: document.getElementById('new-project-modal'),
        modalClose: document.getElementById('new-project-close'),
        modalCancel: document.getElementById('new-project-cancel'),
        newProjectForm: document.getElementById('new-project-form'),
        newProjectName: document.getElementById('new-project-name'),
        newProjectStatus: document.getElementById('new-project-status'),
        importForm: document.getElementById('import-project-form'),
        importName: document.getElementById('import-project-name'),
        importFile: document.getElementById('import-project-file'),
        importStatus: document.getElementById('import-project-status'),
    };

    const state = {
        modalOpen: false,
    };

    if (!els.newProjectBtn) return;

    els.newProjectBtn.addEventListener('click', () => openModal());
    els.modalClose?.addEventListener('click', () => closeModal());
    els.modalCancel?.addEventListener('click', () => closeModal());
    els.modal?.addEventListener('click', (event) => {
        if (event.target === els.modal) {
            closeModal();
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && state.modalOpen) {
            closeModal();
        }
    });

    els.newProjectForm?.addEventListener('submit', async (event) => {
        event.preventDefault();
        const name = (els.newProjectName.value || '').trim();
        if (!name) {
            setStatus(els.newProjectStatus, 'Enter a project name to continue.', true);
            els.newProjectName.focus();
            return;
        }
        setStatus(els.newProjectStatus, 'Creating project…');
        toggleFormDisabled(els.newProjectForm, true);
        try {
            const response = await fetch('/api/projects', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name }),
            });
            const data = await response.json();
            if (!response.ok || data.success === false) {
                throw new Error(data.error || 'Unable to create project');
            }
            window.location.href = `/?project=${encodeURIComponent(data.project)}`;
        } catch (error) {
            console.error(error);
            setStatus(els.newProjectStatus, error.message || 'Unable to create project', true);
        } finally {
            toggleFormDisabled(els.newProjectForm, false);
        }
    });

    els.importForm?.addEventListener('submit', async (event) => {
        event.preventDefault();
        const name = (els.importName.value || '').trim();
        const file = els.importFile.files[0];
        if (!name) {
            setStatus(els.importStatus, 'Add a title for the imported project.', true);
            els.importName.focus();
            return;
        }
        if (!file) {
            setStatus(els.importStatus, 'Choose a layout JSON file to upload.', true);
            els.importFile.focus();
            return;
        }
        const formData = new FormData();
        formData.append('project_name', name);
        formData.append('file', file);
        setStatus(els.importStatus, 'Uploading layout…');
        toggleFormDisabled(els.importForm, true);
        try {
            const response = await fetch('/api/projects/import', {
                method: 'POST',
                body: formData,
            });
            const data = await response.json();
            if (!response.ok || data.success === false) {
                throw new Error(data.error || 'Unable to import project');
            }
            window.location.href = `/?project=${encodeURIComponent(data.project)}`;
        } catch (error) {
            console.error(error);
            setStatus(els.importStatus, error.message || 'Unable to import project', true);
        } finally {
            toggleFormDisabled(els.importForm, false);
        }
    });

    function openModal() {
        if (!els.modal) return;
        els.modal.removeAttribute('hidden');
        els.newProjectName?.focus();
        state.modalOpen = true;
    }

    function closeModal() {
        if (!els.modal) return;
        els.modal.setAttribute('hidden', 'true');
        state.modalOpen = false;
        if (els.newProjectStatus) {
            setStatus(els.newProjectStatus, '');
        }
        els.newProjectForm?.reset();
    }

    function toggleFormDisabled(form, disabled) {
        form?.querySelectorAll('input, button').forEach((element) => {
            element.disabled = disabled;
        });
    }

    function setStatus(target, message, isError = false) {
        if (!target) return;
        target.textContent = message || '';
        target.classList.toggle('status-text--error', Boolean(isError && message));
    }
});
