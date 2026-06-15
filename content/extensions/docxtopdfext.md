---
title: "DocxToPdf"
slug: "docxtopdfext"
kind: "ext"
marketplaceUrl: "https://marketplace.visualstudio.com/items?itemName=michaelsam94.docxtopdfext"
openVsxUrl: "https://open-vsx.org/extension/michaelsam94/docxtopdfext"
githubUrl: "https://github.com/michaelsam94/docxtopdfext"
description: "Convert Microsoft Word .docx files into portable, shareable PDF documents directly inside VS Code — no separate Office suite required, free and fully offline."
thin: false
---

Convert DOCX files to PDF inside VS Code.

## Features

- Command: `DOCX to PDF: Convert File`
- Right-click `.docx` in Explorer and convert directly from the context menu
- Select a `.docx` file and generate a `.pdf` file
- Optional auto-open of the generated PDF file
- Configurable output folder and overwrite behavior

## Extension Settings

- `docxtopdfext.outputFolder`: Target folder for generated PDF files.
  - Empty: save next to source `.docx`
  - Relative: resolved from the first workspace folder
  - Absolute: used directly
- `docxtopdfext.overwriteExisting`: Overwrite existing `.pdf` file if present.
- `docxtopdfext.openAfterConvert`: Open generated PDF file after conversion.

## Publish

1. Install VSCE globally: `npm i -g @vscode/vsce`
2. Login once: `vsce login michaelsam94`
3. Publish: `vsce publish`
