---
title: "PdfToMd"
slug: "pdftomdext"
kind: "ext"
marketplaceUrl: "https://marketplace.visualstudio.com/items?itemName=michaelsam94.pdftomdext"
openVsxUrl: "https://open-vsx.org/extension/michaelsam94/pdftomdext"
githubUrl: "https://github.com/michaelsam94/pdftomdext"
description: "Convert PDF files into editable, AI-ready Markdown text directly inside VS Code — extract content from reports and papers for editing or summaries, offline."
thin: false
---

Convert PDF files to Markdown inside VS Code.

## Features

- Command: `PDF to Markdown: Convert File`
- Right-click `.pdf` in Explorer and convert directly from the context menu
- Select a `.pdf` file and generate a `.md` file
- Optional auto-open of the generated Markdown file
- Configurable output folder and overwrite behavior

## Extension Settings

- `pdftomdext.outputFolder`: Target folder for generated Markdown files.
  - Empty: save next to source `.pdf`
  - Relative: resolved from the first workspace folder
  - Absolute: used directly
- `pdftomdext.overwriteExisting`: Overwrite existing `.md` file if present.
- `pdftomdext.openAfterConvert`: Open generated Markdown file after conversion.

## Publish

1. Install VSCE globally: `npm i -g @vscode/vsce`
2. Login once: `vsce login michaelsam94`
3. Publish: `vsce publish`
