// pytest-aitest Report Scripts

// Initialize Mermaid with dark theme
mermaid.initialize({ 
    startOnLoad: true,
    theme: 'dark',
    securityLevel: 'loose',
    themeVariables: {
        primaryColor: '#4051b5',
        primaryTextColor: '#c9d1d9',
        primaryBorderColor: '#4051b5',
        lineColor: '#8b949e',
        secondaryColor: '#282c34',
        tertiaryColor: '#1e2129',
        background: '#282c34',
        mainBkg: '#282c34',
        noteBkgColor: '#2d333b',
        noteTextColor: '#c9d1d9',
        actorTextColor: '#c9d1d9',
        actorBkg: '#2d323c',
        actorBorder: '#4051b5',
        signalColor: '#c9d1d9',
        signalTextColor: '#c9d1d9',
    }
});

// Copy to clipboard for suggestions
function copyToClipboard(button, text) {
    navigator.clipboard.writeText(text).then(() => {
        const originalText = button.textContent;
        button.textContent = '✓ Copied!';
        button.classList.add('copied');
        setTimeout(() => {
            button.textContent = originalText;
            button.classList.remove('copied');
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy:', err);
        button.textContent = '❌ Error';
        setTimeout(() => {
            button.textContent = '📋 Copy';
        }, 2000);
    });
}

// Fullscreen diagram viewer
function showDiagram(mermaidCode) {
    const overlay = document.getElementById('overlay');
    const content = document.getElementById('overlay-mermaid');
    
    // Set the raw mermaid code as text content (not innerHTML to avoid escaping issues)
    content.textContent = mermaidCode;
    
    // Remove any previous rendering attributes
    content.removeAttribute('data-processed');
    
    overlay.classList.add('active');
    
    // Run mermaid on this element
    mermaid.run({ nodes: [content] }).catch(err => {
        console.error('Mermaid render error:', err);
        // Show the raw code if rendering fails
        content.textContent = 'Error rendering diagram:\n' + mermaidCode;
    });
}

function hideOverlay() {
    document.getElementById('overlay').classList.remove('active');
}

// Close overlay on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') hideOverlay();
});

// Hover popup for side-by-side diagrams
let hoverTimeout = null;
function showDiagramHover(element, mermaidCode) {
    clearTimeout(hoverTimeout);
    const popup = document.getElementById('diagram-hover-popup');
    const content = document.getElementById('hover-mermaid');
    content.innerHTML = mermaidCode;
    popup.classList.add('active');
    mermaid.run({ nodes: [content] });
}

function hideDiagramHover() {
    hoverTimeout = setTimeout(() => {
        document.getElementById('diagram-hover-popup').classList.remove('active');
    }, 100);
}

function keepDiagramHover() {
    clearTimeout(hoverTimeout);
}

// Side-by-side test selector
function showSideBySideTest(testId) {
    // Hide all groups
    document.querySelectorAll('.side-by-side-group').forEach(group => {
        group.classList.remove('active');
    });
    // Show selected group
    const selected = document.getElementById(testId);
    if (selected) {
        selected.classList.add('active');
        // Re-render mermaid diagrams in the newly visible group
        mermaid.run({ nodes: selected.querySelectorAll('.mermaid') });
    }
}
