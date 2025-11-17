// Utility functions
const $ = (s, p=document) => p.querySelector(s);
const $$ = (s, p=document) => p.querySelectorAll(s);
const E = (t, a, h) => Object.assign(document.createElement(t), a, h ? {innerHTML: h} : {});
const C = (m) => { const t = E('div', {className: 'toast'}, m); document.body.appendChild(t); setTimeout(() => t.remove(), 2400); };
const clamp = (v, min, max) => Math.min(Math.max(v, min), max);

function genId() { return 'b_' + Date.now() + Math.random().toString(36).substr(2, 5); }
function sampleContent(t) {
    const samples = {headline: 'Headline text', body: 'Body text here...', image: '<div class="image-placeholder">Image</div>'};
    return samples[t] || 'Edit me';
}

// Export these functions
window.utils = { $, $$, E, C, clamp, genId, sampleContent };