---
title: "DocxViewer"
slug: "docxviewerext"
kind: "ext"
marketplaceUrl: "https://marketplace.visualstudio.com/items?itemName=michaelsam94.docxviewerext"
openVsxUrl: "https://open-vsx.org/extension/michaelsam94/docxviewerext"
githubUrl: "https://github.com/michaelsam94/docxviewerext"
description: "Preview DOCX files quickly from VS Code."
thin: false
---

Preview DOCX files quickly inside VS Code.

## Features

- Command: `DOCX Viewer: Open File`
- Right-click `.docx` in Explorer and open directly from the context menu
- Open selected DOCX in an in-extension preview panel
- Commands: `DOCX Viewer: Zoom In`, `DOCX Viewer: Zoom Out`, `DOCX Viewer: Reset Zoom`
- Zoom shortcut in preview: `Cmd + Mouse Wheel` (macOS), `Ctrl + Mouse Wheel` (Windows/Linux)

## Extension Settings

- `docxviewerext.openToSide`: Open DOCX preview in side editor.
- `docxviewerext.preserveFocus`: Keep focus in current editor after opening preview.

## Publish

1. Install VSCE globally: `npm i -g @vscode/vsce`
2. Login once: `vsce login michaelsam94`
3. Publish: `vsce publish`
