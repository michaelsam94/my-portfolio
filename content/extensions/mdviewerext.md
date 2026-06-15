---
title: "MdViewer"
slug: "mdviewerext"
kind: "ext"
marketplaceUrl: "https://marketplace.visualstudio.com/items?itemName=michaelsam94.mdviewerext"
openVsxUrl: "https://open-vsx.org/extension/michaelsam94/mdviewerext"
githubUrl: "https://github.com/michaelsam94/mdviewerext"
description: "Preview rendered Markdown instantly inside VS Code while you edit, with a clean live view of headings, lists, tables, and code blocks — free, fast, and offline."
thin: false
---

Preview Markdown files quickly inside VS Code.

## Features

- Command: `Markdown Viewer: Open File`
- Right-click `.md` in Explorer and open directly from the context menu
- Open selected Markdown in an in-extension preview panel
- Commands: `Markdown Viewer: Zoom In`, `Markdown Viewer: Zoom Out`, `Markdown Viewer: Reset Zoom`
- Zoom shortcut in preview: `Cmd + Mouse Wheel` (macOS), `Ctrl + Mouse Wheel` (Windows/Linux)

## Extension Settings

- `mdviewerext.openToSide`: Open Markdown preview in side editor.
- `mdviewerext.preserveFocus`: Keep focus in current editor after opening preview.

## Publish

1. Install VSCE globally: `npm i -g @vscode/vsce`
2. Login once: `vsce login michaelsam94`
3. Publish: `vsce publish`
