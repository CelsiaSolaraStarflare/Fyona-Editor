document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("settings-form");
    const status = document.getElementById("settings-status");
    const localSection = document.getElementById("local-settings");
    const onlineSection = document.getElementById("online-settings");
    const modeInputs = Array.from(document.querySelectorAll("input[name=mode]"));
    const enableThinkingInput = document.getElementById("enable-thinking");
    const thinkingBudgetInput = document.getElementById("thinking-budget");
    const themeSelect = document.getElementById("theme");
    const DEFAULT_THEME = "blue-glass";
    const DEFAULT_TONE = "light";
    const themeModeInputs = Array.from(document.querySelectorAll("input[name=theme_mode]"));

    const setStatus = (message, options = {}) => {
        if (!status) {
            return;
        }
        status.textContent = message || "";
        status.dataset.state = options.state || "";
    };

    const applyModeVisibility = (mode) => {
        if (mode === "online") {
            localSection?.setAttribute("hidden", "hidden");
            onlineSection?.removeAttribute("hidden");
        } else {
            onlineSection?.setAttribute("hidden", "hidden");
            localSection?.removeAttribute("hidden");
        }
    };

    const loadSettings = async () => {
        try {
            const response = await fetch("/api/settings", { method: "GET" });
            if (!response.ok) {
                throw new Error(`Failed to load settings (${response.status})`);
            }
            const settings = await response.json();
            if (settings?.mode) {
                const mode = String(settings.mode).toLowerCase();
                const target = modeInputs.find((input) => input.value === mode);
                if (target) {
                    target.checked = true;
                    applyModeVisibility(mode);
                }
            }
            if (typeof settings?.local_model === "string") {
                const localField = document.getElementById("local-model");
                if (localField) {
                    localField.value = settings.local_model;
                }
            }
            if (typeof settings?.online_model === "string") {
                const onlineField = document.getElementById("online-model");
                if (onlineField) {
                    onlineField.value = settings.online_model;
                }
            }
            if (typeof settings?.online_enable_thinking === "boolean" && enableThinkingInput) {
                enableThinkingInput.checked = settings.online_enable_thinking;
            }
            if (Number.isFinite(Number(settings?.online_thinking_budget)) && thinkingBudgetInput) {
                thinkingBudgetInput.value = Number(settings.online_thinking_budget);
            }
            if (typeof settings?.theme === "string" && themeSelect) {
                themeSelect.value = settings.theme;
                applyThemePreview(settings.theme, settings.theme_mode);
            } else if (themeSelect) {
                applyThemePreview(themeSelect.value || DEFAULT_THEME);
            }
            if (themeModeInputs.length) {
                const desiredTone = typeof settings?.theme_mode === "string" ? settings.theme_mode : DEFAULT_TONE;
                const matching = themeModeInputs.find((input) => input.value === desiredTone);
                if (matching) {
                    matching.checked = true;
                }
            }
        } catch (error) {
            setStatus(error?.message || "Unable to load settings", { state: "error" });
        }
    };

    modeInputs.forEach((input) => {
        input.addEventListener("change", (event) => {
            applyModeVisibility(event.target.value);
        });
    });

    const applyThemePreview = (theme, tone) => {
        const targetTheme = typeof theme === "string" && theme.trim() ? theme.trim() : DEFAULT_THEME;
        const toneCandidate =
            typeof tone === "string"
                ? tone
                : themeModeInputs.find((input) => input.checked)?.value || DEFAULT_TONE;
        const targetTone = toneCandidate === "dark" ? "dark" : DEFAULT_TONE;
        if (document.body) {
            document.body.setAttribute("data-theme", targetTheme);
            document.body.setAttribute("data-tone", targetTone);
        }
    };

    themeSelect?.addEventListener("change", (event) => {
        applyThemePreview(event.target.value);
    });

    themeModeInputs.forEach((input) => {
        input.addEventListener("change", () => {
            applyThemePreview(themeSelect?.value || DEFAULT_THEME);
        });
    });

    form?.addEventListener("submit", async (event) => {
        event.preventDefault();
        const formData = new FormData(form);
        const payload = Object.fromEntries(formData.entries());
        payload.mode = payload.mode || "local";
        payload.online_enable_thinking = formData.has("online_enable_thinking");
        payload.theme = payload.theme || DEFAULT_THEME;
        payload.theme_mode = formData.get("theme_mode") || DEFAULT_TONE;
        setStatus("Saving…", { state: "pending" });
        try {
            const response = await fetch("/api/settings", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await response.json();
            if (!response.ok || data?.error) {
                throw new Error(data?.error || `Failed to save settings (${response.status})`);
            }
            setStatus("Settings saved.", { state: "ok" });
        } catch (error) {
            setStatus(error?.message || "Failed to save settings", { state: "error" });
        }
    });

    applyThemePreview(themeSelect?.value || DEFAULT_THEME, DEFAULT_TONE);
    void loadSettings();
});
