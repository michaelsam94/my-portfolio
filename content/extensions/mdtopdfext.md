---
title: "MdToPdf"
slug: "mdtopdfext"
kind: "ext"
marketplaceUrl: "https://marketplace.visualstudio.com/items?itemName=michaelsam94.mdtopdfext"
openVsxUrl: "https://open-vsx.org/extension/michaelsam94/mdtopdfext"
githubUrl: "https://github.com/michaelsam94/mdtopdfext"
description: "Convert Markdown files into clean, shareable PDF documents inside VS Code — turn READMEs, notes, and docs into portable PDFs in one step, free and offline."
thin: false
---

Convert Markdown files to PDF inside VS Code.

## Features

- Command: `Markdown to PDF: Convert File`
- Right-click `.md` in Explorer and convert directly from the context menu
- Select a `.md` file and generate a `.pdf` file
- Optional auto-open of the generated PDF file
- Configurable output folder and overwrite behavior

## Extension Settings

- `mdtopdfext.outputFolder`: Target folder for generated PDF files.
  - Empty: save next to source `.md`
  - Relative: resolved from the first workspace folder
  - Absolute: used directly
- `mdtopdfext.overwriteExisting`: Overwrite existing `.pdf` file if present.
- `mdtopdfext.openAfterConvert`: Open generated PDF file after conversion.
- `mdtopdfext.chromeExecutablePath`: Optional path to Chrome/Chromium executable used by the converter.

## Publish

1. Install VSCE globally: `npm i -g @vscode/vsce`
2. Login once: `vsce login michaelsam94`
3. Publish: `vsce publish`
