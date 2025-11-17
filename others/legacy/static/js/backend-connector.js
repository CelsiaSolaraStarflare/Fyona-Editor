/**
 * BackendConnector centralizes HTTP interactions with the Fiona backend.
 * It wraps fetch with project-aware helpers and consistent error handling.
 */
(function attachBackendConnector(global) {
    const defaultOptions = {
        credentials: "same-origin",
        headers: {},
    };

    class BackendRequestError extends Error {
        constructor(message, response, payload) {
            super(message);
            this.name = "BackendRequestError";
            this.status = response?.status ?? null;
            this.response = response;
            this.payload = payload;
        }
    }

    class BackendConnector {
        constructor(options = {}) {
            const { baseUrl = "", fetchImpl = global.fetch.bind(global) } = options;
            this.baseUrl = baseUrl.replace(/\/$/, "");
            this.fetchImpl = fetchImpl;
        }

        buildUrl(path) {
            if (!path) {
                return this.baseUrl || "/";
            }
            if (/^https?:\/\//i.test(path)) {
                return path;
            }
            const normalized = path.startsWith("/") ? path : `/${path}`;
            return `${this.baseUrl}${normalized}`;
        }

        async request(path, options = {}) {
            const {
                method = "GET",
                body,
                headers = {},
                expect = "json",
                signal,
                raw,
            } = options;

            const url = this.buildUrl(path);
            const init = {
                ...defaultOptions,
                method,
                headers: { ...defaultOptions.headers, ...headers },
                signal,
            };

            if (body !== undefined) {
                if (raw) {
                    init.body = body;
                } else if (body instanceof FormData) {
                    init.body = body;
                } else if (typeof body === "string") {
                    init.body = body;
                    init.headers["Content-Type"] = init.headers["Content-Type"] || "application/json";
                } else {
                    init.body = JSON.stringify(body);
                    init.headers["Content-Type"] = init.headers["Content-Type"] || "application/json";
                }
            }

            let response;
            try {
                response = await this.fetchImpl(url, init);
            } catch (networkError) {
                throw new BackendRequestError(networkError.message || "Network error", null);
            }

            if (!response.ok) {
                let errorPayload = null;
                try {
                    errorPayload = await response.clone().json();
                } catch (_) {
                    try {
                        errorPayload = await response.clone().text();
                    } catch (_) {
                        errorPayload = null;
                    }
                }
                const message =
                    (errorPayload && (errorPayload.error || errorPayload.message)) ||
                    `Request failed with status ${response.status}`;
                throw new BackendRequestError(message, response, errorPayload);
            }

            switch (expect) {
                case "blob":
                    return response.blob();
                case "text":
                    return response.text();
                case "json":
                default:
                    if (response.status === 204) {
                        return null;
                    }
                    return response.json();
            }
        }

        get(path, options) {
            return this.request(path, { ...options, method: "GET" });
        }

        post(path, body, options) {
            return this.request(path, { ...options, method: "POST", body });
        }

        async listProjects() {
            return this.get("/projects");
        }

        async fetchLayout(project) {
            const query = project ? `?project=${encodeURIComponent(project)}` : "";
            return this.get(`/layout${query}`);
        }

        async saveLayout(layout, project) {
            if (!layout || typeof layout !== "object") {
                throw new Error("layout must be an object");
            }
            const payload = { layout, project };
            return this.post("/save-layout", payload);
        }

        async loadSettings() {
            return this.get("/api/settings");
        }

        async saveSettings(settings) {
            return this.post("/api/settings", settings);
        }

        async assistantChat(payload) {
            return this.post("/api/assistant/chat", payload);
        }

        async exportPdf(payload) {
            return this.post("/export/pdf", payload, { expect: "blob" });
        }

        async loadDemoLayout() {
            return this.get("/demo-layout");
        }

        async createSnapshot(layout, project, label) {
            const body = { layout, project, label };
            return this.post("/time-machine/snapshot", body);
        }

        async fetchTimeMachineHistory(project) {
            const query = project ? `?project=${encodeURIComponent(project)}` : "";
            return this.get(`/time-machine/history${query}`);
        }

        async previewSnapshot(commit, project) {
            const body = { commit, project, preview: true };
            return this.post("/time-machine/revert", body);
        }

        async applySnapshot(commit, project) {
            const body = { commit, project, preview: false };
            return this.post("/time-machine/revert", body);
        }
    }

    global.BackendConnector = BackendConnector;
    global.BackendRequestError = BackendRequestError;
    if (!global.backendConnector) {
        global.backendConnector = new BackendConnector();
    }
})(typeof window !== "undefined" ? window : globalThis);
