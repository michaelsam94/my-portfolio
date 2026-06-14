---
title: "DocxToMd"
slug: "docxtomdext"
kind: "ext"
marketplaceUrl: "https://marketplace.visualstudio.com/items?itemName=michaelsam94.docxtomdext"
openVsxUrl: "https://open-vsx.org/extension/michaelsam94/docxtomdext"
githubUrl: "https://github.com/michaelsam94/docxtomdext"
description: "Convert DOCX files to Markdown from VS Code."
thin: false
---

Convert DOCX files to Markdown inside VS Code.

## Features

- Command: `DOCX to Markdown: Convert File`
- Recovery command: `DOCX to Markdown: Reload VS Code Window`
- Right-click `.docx` in Explorer and convert directly from the context menu
- Select a `.docx` file and generate a `.md` file
- Optional auto-open of the generated Markdown file
- Configurable output folder and overwrite behavior

## Extension Settings

- `docxtomdext.outputFolder`: Target folder for generated Markdown files.
  - Empty: save next to source `.docx`
  - Relative: resolved from the first workspace folder
  - Absolute: used directly
- `docxtomdext.overwriteExisting`: Overwrite existing `.md` file if present.
- `docxtomdext.openAfterConvert`: Open generated Markdown file after conversion.
