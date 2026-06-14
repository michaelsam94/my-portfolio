---
title: "PdfViewer"
slug: "pdfviewerext"
kind: "ext"
marketplaceUrl: "https://marketplace.visualstudio.com/items?itemName=michaelsam94.pdfviewerext"
openVsxUrl: "https://open-vsx.org/extension/michaelsam94/pdfviewerext"
githubUrl: "https://github.com/michaelsam94/pdfviewerext"
description: "Open PDF files quickly from VS Code."
thin: false
---

Open PDF files quickly inside VS Code.

## Features

- Command: `PDF Viewer: Open File`
- Right-click `.pdf` in Explorer and open directly from the context menu
- Open selected PDF in an in-extension preview panel
- Commands: `PDF Viewer: Zoom In`, `PDF Viewer: Zoom Out`, `PDF Viewer: Reset Zoom`
- Zoom shortcut in preview: `Cmd + Mouse Wheel` (macOS), `Ctrl + Mouse Wheel` (Windows/Linux)
- Optional preserve-focus behavior

## Extension Settings

- `pdfviewerext.openToSide`: Open PDFs in side editor.
- `pdfviewerext.preserveFocus`: Keep focus in current editor after opening PDF.

## Publish

1. Install VSCE globally: `npm i -g @vscode/vsce`
2. Login once: `vsce login michaelsam94`
3. Publish: `vsce publish`
