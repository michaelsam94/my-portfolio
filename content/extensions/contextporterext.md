---
title: "Context Porter"
slug: "contextporterext"
kind: "ext"
marketplaceUrl: "https://marketplace.visualstudio.com/items?itemName=michaelsam94.contextporterext"
openVsxUrl: "https://open-vsx.org/extension/michaelsam94/contextporterext"
githubUrl: "https://github.com/michaelsam94/contextporterext"
description: "Export AI session and project context to Markdown for handoff."
thin: false
---

**Context Porter** is a [Visual Studio Code](https://code.visualstudio.com/) extension that exports AI session and project context to **Markdown** so you can hand it off to other tools (ChatGPT, Claude, docs, tickets) without retyping everything.

Repository: [github.com/michaelsam94/contextporterext](https://github.com/michaelsam94/contextporterext)

**Compatibility:** Development and day-to-day use are in **Cursor**. The same VSIX may run in stock **VS Code** or **Claude**-based / other VS Code forks, but those environments are **not fully tested** yet—if something breaks outside Cursor, open an issue with your editor and version.

## Features

- **New export file** — Creates a timestamped Markdown file under context-exports/ with YAML front matter, then a **Session snapshot**: workspace **root listing**, a **sample of project files** (scanned `*.md`, `*.ts`, etc., excluding `node_modules`), **tab bar titles**, open buffers, **git branch** (searching upward for a repo), optional **selected text**, plus template sections for summary and transcript.
- **Cursor Composer / chat (experimental)** — When running **inside Cursor**, the extension can **read local SQLite** used by Cursor (`globalStorage/state.vscdb` and the current workspace’s `workspaceStorage/.../state.vscdb`) and pull rows whose keys look like Composer / chat / bubble data. Prompts, replies, and “thinking” may appear inside those JSON blobs. This is **best-effort** and **breaks when Cursor changes storage**; there is still **no official API**. Toggle with `contextporterext.importCursorLocalHistory`. If import is empty, paste from the chat panel into **Transcript** or use **Append Clipboard to Session Log**.
- **Session log** — Append titled notes or **clipboard** content to `SESSION.md` in the same folder.
- **Secret-safe by default** — Heuristic redaction for common tokens (API keys, JWTs, `Bearer` headers, PEM blocks, env-style assignments, and more). Optional extra regex list in settings.
- **Path privacy** — Optional omission of absolute workspace paths in front matter (folder names only), suitable for external prompts.
- **Optional AI review (VS Code)** — When the [Language Model API](https://code.visualstudio.com/api/extension-guides/language-model) is available (for example with **GitHub Copilot Chat** in VS Code), you can send the **sanitized** export to the IDE-connected model for a second-pass leak check. Forks such as Cursor may not expose this API; heuristic redaction still applies.

## Commands

Open the Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`):

| Command | Description |
|--------|-------------|
| **Context Porter: New Export File** | Create a new context Markdown file. |
| **Context Porter: Append to Session Log** | Append an optional title and short note to the session log. |
| **Context Porter: Append Clipboard to Session Log** | Append clipboard text (sanitized) in a fenced block. |
| **Context Porter: AI Review Active File (IDE model)** | Sanitize the open file and append an IDE model review section (when available). |

## Settings

| ID | Default | Description |
|----|---------|-------------|
| `contextporterext.exportFolder` | `context-exports` | Output folder relative to the workspace folder. |
| `contextporterext.sessionLogFileName` | `SESSION.md` | Session log file name inside the export folder. |
| `contextporterext.toolLabel` | _(empty)_ | Override the `tool` field in front matter; otherwise uses the app name. |
| `contextporterext.sanitizeExports` | `true` | Enable heuristic secret redaction. |
| `contextporterext.omitFullWorkspacePaths` | `true` | Omit absolute paths in front matter. |
| `contextporterext.extraRedactRegex` | `[]` | Additional RegExp sources for custom redaction. |
| `contextporterext.aiReview` | `ask` | `off` / `ask` / `always` — optional LM review after a new export. |
| `contextporterext.importCursorLocalHistory` | `true` | In **Cursor**, try to import Composer/chat-related rows from local SQLite into new exports (experimental). |

## Privacy and limitations

- Automatic redaction is **best-effort**, not a guarantee. **Review** exports before sharing.
- **AI review** sends sanitized text to your IDE’s language model provider when you confirm (or when set to `always`). Read your provider’s terms.
- This extension does **not** read proprietary chat databases from Cursor or other vendors; it focuses on **files you export** through these commands.
