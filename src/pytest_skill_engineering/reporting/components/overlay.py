"""Overlay component - fullscreen diagram viewer."""

from __future__ import annotations

from htpy import Node, button, div, style
from markupsafe import Markup


def overlay() -> Node:
    """Render the fullscreen overlay for diagram viewing.

    Returns:
        htpy Node for the overlay and hover popup.
    """
    overlay_cls = (
        "fixed inset-0 bg-black/80 backdrop-blur-sm z-50 hidden items-center justify-center p-8"
    )
    close_btn_cls = (
        "absolute top-4 right-4 w-10 h-10 flex items-center justify-center "
        "text-2xl text-text-muted hover:text-text-light bg-surface-card "
        "rounded-full border border-white/10 transition-colors"
    )
    content_cls = (
        "w-[90vw] h-[85vh] overflow-auto bg-surface-card rounded-lg p-6 "
        "shadow-material-lg flex items-center justify-center"
    )
    hover_cls = (
        "fixed z-40 bg-surface-card rounded-lg shadow-material-lg "
        "border border-white/10 p-4 hidden max-w-xl"
    )
    hover_onclick = (
        "hideOverlay(); this.classList.add('hidden'); "
        "showDiagram(document.getElementById('hover-mermaid').innerHTML);"
    )
    return [
        # Main fullscreen overlay
        div(
            id="overlay",
            class_=overlay_cls,
            onclick="hideOverlay()",
        )[
            button(
                class_=close_btn_cls,
                onclick="hideOverlay()",
            )["✕"],
            div(
                class_=content_cls,
                onclick="event.stopPropagation()",
            )[div(".mermaid.w-full.h-full", id="overlay-mermaid"),],
        ],
        # Hover popup for side-by-side diagrams
        div(
            id="diagram-hover-popup",
            class_=hover_cls,
            onmouseenter="keepDiagramHover()",
            onmouseleave="hideDiagramHover()",
            onclick=hover_onclick,
        )[div(".mermaid", id="hover-mermaid"),],
        # Styles for overlay behavior
        style[
            Markup("""
#overlay.active { display: flex !important; }
#diagram-hover-popup.active { display: block !important; }

/* Scale the mermaid SVG in overlay to fill available space */
#overlay-mermaid svg {
    max-width: 100%;
    max-height: 100%;
    width: auto;
    height: auto;
    min-height: 60vh;
}
""")
        ],
    ]
