import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";

const EXTENSIONS = {
  docxviewerext: {
    name: "DOCX Viewer",
    action: "preview Word documents",
    input: "DOCX files",
    output: "readable document previews",
    audience: "developers, writers, reviewers, and support teams",
    workflow: "checking a contract, product brief, release note, or exported report without leaving VS Code",
  },
  docxtomdext: {
    name: "DOCX to Markdown",
    action: "convert Word documents into Markdown",
    input: "DOCX files",
    output: "clean Markdown content",
    audience: "technical writers, documentation teams, open-source maintainers, and engineers",
    workflow: "moving specs, drafts, and product notes from Word into a docs repository",
  },
  docxtopdfext: {
    name: "DOCX to PDF",
    action: "export Word documents as PDF files",
    input: "DOCX files",
    output: "portable PDF documents",
    audience: "engineers, consultants, students, and operations teams",
    workflow: "turning proposals, release notes, reports, and checklists into shareable PDFs",
  },
  mdtopdfext: {
    name: "Markdown to PDF",
    action: "turn Markdown into PDF",
    input: "Markdown files",
    output: "publication-ready PDFs",
    audience: "developers, technical writers, founders, and product teams",
    workflow: "shipping README content, runbooks, proposals, or release notes as polished PDF files",
  },
  mdviewerext: {
    name: "Markdown Viewer",
    action: "preview Markdown documents",
    input: "Markdown files",
    output: "readable rendered previews",
    audience: "developers, documentation writers, reviewers, and maintainers",
    workflow: "reviewing README files, changelogs, docs pages, and issue templates while editing them",
  },
  pdftomdext: {
    name: "PDF to Markdown",
    action: "convert PDF files into Markdown",
    input: "PDF documents",
    output: "editable Markdown content",
    audience: "researchers, developers, documentation teams, and AI workflow builders",
    workflow: "extracting useful text from reports, papers, manuals, and exported documents",
  },
  pdfviewerext: {
    name: "PDF Viewer",
    action: "preview PDF files",
    input: "PDF documents",
    output: "fast in-editor PDF previews",
    audience: "developers, researchers, support teams, and students",
    workflow: "opening specs, invoices, papers, or product documents while staying inside VS Code",
  },
};

const sharedPrinciples = [
  "The extension is designed for people who already live in VS Code and do not want a separate desktop app for every document task.",
  "The main goal is to reduce context switching, keep files close to the project, and make document work feel like part of the developer workflow.",
  "Each page explains practical use cases, decision points, limitations, and quality checks so search engines and AI answer systems have enough context.",
  "The wording is intentionally direct: what the extension does, when to use it, how it fits into a team process, and what to verify before sharing output.",
];

function paragraphs(items) {
  return items.map((item) => `<p>${item}</p>`).join("\n");
}

function list(items) {
  return `<ul>${items.map((item) => `<li>${item}</li>`).join("")}</ul>`;
}

function extensionArticle(slug, ext) {
  return `
    <section class="longform" id="extension-guide">
      <h2>${ext.name} guide: when to use it and what to check</h2>
      ${paragraphs([
        `${ext.name} helps you ${ext.action} directly inside Visual Studio Code. The extension is useful when your source files, documentation, notes, and project context are already in the editor, and you want to avoid jumping between multiple tools just to inspect or transform ${ext.input}.`,
        `The practical value is speed and focus. Instead of opening another application, hunting for the right export menu, saving a temporary file, and returning to the workspace, you can keep the document task close to the code, docs, or research folder where the work started.`,
        `This matters for ${ext.audience}. A small document task can interrupt a deep work session, especially when the document is part of a pull request, release checklist, customer report, or internal knowledge base. ${ext.name} keeps that task visible and repeatable.`,
        `A common workflow is ${ext.workflow}. In that situation, the extension is not trying to replace a full office suite. It is meant to handle the focused document step that blocks the next engineering, writing, or review action.`,
      ])}

      <h2>Best use cases</h2>
      ${paragraphs([
        `Use ${ext.name} when the source document is connected to a project and the next action also happens in VS Code. That includes reviewing documentation, preparing release material, checking generated files, or moving content into a repository-friendly format.`,
        `It is also helpful for AI-assisted workflows. If you need ${ext.output} before summarizing, indexing, reviewing, or committing content, keeping the conversion near the workspace makes the process easier to audit.`,
      ])}
      ${list([
        `Review ${ext.input} without losing the current workspace context.`,
        `Create ${ext.output} as part of documentation, research, or delivery work.`,
        `Keep document tasks close to version-controlled files and project notes.`,
        `Check generated content before sharing it with teammates or clients.`,
        `Support repeatable workflows for specs, reports, runbooks, and release material.`,
      ])}

      <h2>How to use the extension well</h2>
      ${paragraphs([
        `Start with a clean source file and confirm that the file opens correctly in VS Code. If the file came from email, chat, cloud storage, or an export pipeline, save a local copy in the workspace first so the input is easy to find again.`,
        `Run the extension on one representative file before processing a batch of similar documents. This gives you a quick quality check and helps you spot formatting, missing text, unsupported embedded objects, or layout changes before they spread into more files.`,
        `After you create ${ext.output}, review headings, lists, links, tables, images, and code blocks. Document formats often store structure differently, so a human review is still important before publishing, committing, or sending the result to another team.`,
        `If the document contains sensitive information, treat the generated output with the same care as the original. Keep private files out of public repositories, remove temporary artifacts when they are no longer needed, and avoid committing customer or credential data by accident.`,
      ])}

      <h2>Quality checklist</h2>
      ${list([
        "Open the original file and confirm it is the version you intend to process.",
        "Check the generated output for headings, spacing, tables, links, and images.",
        "Compare a few important paragraphs against the source document.",
        "Rename the output file clearly so teammates understand what it contains.",
        "Review privacy, licensing, and repository rules before committing or sharing files.",
        "Keep a copy of the original document when the conversion is part of a formal process.",
      ])}

      <h2>Limits and expectations</h2>
      ${paragraphs([
        `${ext.name} is built for focused document viewing and conversion inside VS Code. It is not a replacement for a full document authoring suite, a compliance archive, or a pixel-perfect publishing system.`,
        `Complex documents can contain embedded fonts, tracked changes, comments, macros, scanned pages, unusual tables, or images that need manual review. The safest workflow is to use the extension for speed, then review the result before treating it as final.`,
        `If your organization has strict legal, medical, financial, or security requirements, use the extension as a developer convenience and keep the official review process in place. Good tooling should make careful work faster, not remove accountability.`,
      ])}

      <h2>Related MichaelSam94 document tools</h2>
      ${paragraphs([
        `This extension is part of a broader set of MichaelSam94 VS Code document tools. The collection includes viewers and converters for Markdown, PDF, and DOCX workflows, so you can choose the smallest tool that matches the current document task.`,
        `If your workflow moves between several formats, visit the VS Code extensions hub to compare the tools and choose the viewer or converter that fits your project.`,
      ])}
      <p><a href="/vscode/">Browse all MichaelSam94 VS Code extensions</a>.</p>
    </section>
  `;
}

function hubArticle() {
  return `
    <section class="longform" id="vscode-extension-guide">
      <h2>MichaelSam94 VS Code extensions: document tools for developer workflows</h2>
      ${paragraphs([
        "The MichaelSam94 VS Code extension collection focuses on practical document work inside the editor. The tools help developers, writers, students, researchers, and product teams view or convert Markdown, PDF, and DOCX files without leaving the workspace.",
        "The purpose is not to turn VS Code into a full office suite. The purpose is to remove small workflow interruptions. If a document task starts inside a repository, docs folder, support case, release checklist, or research workspace, it is often faster to handle that task where the surrounding context already lives.",
        "This hub brings the extensions together so you can choose the right tool for the current file format. Some tools are viewers, which help you inspect content quickly. Other tools are converters, which help you create a more useful format for editing, publishing, review, or AI-assisted analysis.",
        "The collection is especially useful when document work is part of software delivery. Teams often move between README files, PDFs, exported reports, DOCX drafts, release notes, proposals, internal specs, and customer-facing documents. These extensions keep that movement visible and repeatable.",
      ])}

      <h2>Which extension should you choose?</h2>
      ${paragraphs([
        "Choose a viewer when you need to inspect a file and make a decision. A PDF viewer or DOCX viewer is useful when you want to keep a specification, report, invoice, or brief next to the code or documentation you are editing.",
        "Choose a converter when the next step requires a different format. DOCX to Markdown helps move drafts into a repository. Markdown to PDF helps create a shareable artifact from docs. PDF to Markdown helps extract useful text from a report or paper before editing or summarizing it.",
      ])}
      ${list([
        "Use PDF Viewer when you need to read a PDF beside code, docs, or notes.",
        "Use DOCX Viewer when a Word document needs quick inspection inside VS Code.",
        "Use Markdown Viewer when you want rendered Markdown feedback while editing.",
        "Use Markdown to PDF when a README, runbook, or proposal needs a shareable PDF.",
        "Use DOCX to Markdown when Word content needs to become repository-friendly text.",
        "Use DOCX to PDF when a document needs a portable final format.",
        "Use PDF to Markdown when a PDF needs to become editable or AI-ready text.",
      ])}

      <h2>Common workflows</h2>
      ${paragraphs([
        "A documentation workflow often starts with rough notes, becomes Markdown, and ends as a published page or PDF. Keeping preview and conversion tools in VS Code makes it easier to catch formatting problems before a teammate or customer sees them.",
        "A product workflow may start with a DOCX brief from a stakeholder. Converting that brief into Markdown can make it easier to discuss in pull requests, split into tasks, or store with the codebase. Viewing the original document beside the generated output helps reviewers confirm nothing important was lost.",
        "A research workflow may start with a PDF paper, report, or exported document. Converting or previewing that PDF inside the workspace can help you extract useful sections, compare notes, and prepare content for summaries, embeddings, or internal knowledge bases.",
        "A release workflow may include Markdown changelogs, PDF notes, DOCX drafts, and customer-facing assets. A small set of editor-based tools can reduce the number of manual steps between writing, checking, exporting, and sharing.",
      ])}

      <h2>Quality and review checklist</h2>
      ${paragraphs([
        "Document conversion is useful, but it should still be reviewed. File formats store headings, images, tables, code blocks, and links in different ways, so a quick check prevents small formatting issues from becoming public mistakes.",
        "Before sharing output, compare important paragraphs against the source file. Check links, headings, numbered lists, images, and tables. If the result will be committed to a repository, review the diff and make sure generated files belong in version control.",
      ])}
      ${list(sharedPrinciples)}

      <h2>Why this matters for teams</h2>
      ${paragraphs([
        "Teams move faster when small tasks are easy to repeat. If a process depends on one person opening a separate app and exporting a file manually, the process is harder to document and easier to skip. Editor-based document tools make the workflow easier to explain.",
        "They also help with onboarding. A new teammate can read the README, install the recommended extension, and follow the same steps as the rest of the team. That consistency matters when documentation, release notes, reports, and customer files are part of normal delivery.",
        "The best use of these extensions is practical and modest: keep document work close to the project, reduce context switching, improve review habits, and make generated files easier to inspect before they are published or shared.",
      ])}
    </section>
  `;
}

function blogHubArticle() {
  return `
    <section class="longform" id="engineering-blog-guide">
      <h2>Engineering blog: practical notes from Android, mobile, infrastructure, and AI work</h2>
      ${paragraphs([
        "The Michael Samuel Naeem engineering blog is a place for practical software notes rather than abstract theory. The posts focus on lessons from Android development, Kotlin, Jetpack Compose, Flutter, Riverpod, OCPP, WebSocket systems, EV charging platforms, real-time interfaces, and production delivery.",
        "The goal is to make each article useful for a developer, technical lead, founder, or product team that needs to understand how a decision works in practice. A good post should answer what changed, why the decision mattered, what tradeoffs appeared, and how the same idea could help another project.",
        "This blog hub collects those posts in one crawlable index. It gives search engines and AI answer systems enough context to understand the themes behind the articles, not only the individual titles. The main themes are mobile architecture, reactive state, reliable infrastructure, developer experience, and measurable delivery outcomes.",
      ])}

      <h2>What the articles cover</h2>
      ${paragraphs([
        "Android and Kotlin posts usually focus on production habits. That includes state ownership, UI performance, lifecycle safety, migration strategy, release reliability, and the choices that make a mobile app easier to maintain after the first launch.",
        "Jetpack Compose articles focus on keeping composables predictable. Topics include derived state, stable models, scroll performance, interop with legacy screens, and the difference between code that works in a demo and code that survives a large app.",
        "Flutter and Riverpod articles focus on real-time state, provider boundaries, WebSocket data, map interfaces, and avoiding rebuild storms. These are common problems in EV charging, location-heavy products, dashboards, and live operational tools.",
        "Infrastructure posts focus on OCPP, WebSocket communication, charging state, network failure, local discovery, and resilient platform behavior. The writing is grounded in systems where a dropped connection or unclear state can become a real product problem.",
      ])}

      <h2>Who should read this blog?</h2>
      ${paragraphs([
        "Developers can use the blog to compare implementation patterns and avoid common mistakes. The posts are written to be concrete enough for engineers who want a practical starting point before they adapt the idea to their own codebase.",
        "Technical leads can use the posts as discussion material for architecture reviews, migration planning, and team standards. The writing often explains why a pattern matters, not just what syntax to paste into a project.",
        "Founders and product leaders can use the blog to understand how technical decisions affect delivery speed, reliability, and user experience. The articles connect implementation details to outcomes such as uptime, performance, maintainability, and release confidence.",
        "AI-assisted development workflows can also benefit from the blog because the articles include direct explanations, examples, and decision rules. That makes the content easier to summarize, cite, and transform into checklists or implementation plans.",
      ])}

      <h2>How to use the posts</h2>
      ${list([
        "Read the article once for the core idea before copying any pattern into your project.",
        "Compare the described tradeoffs with your app size, team structure, release cycle, and risk level.",
        "Turn useful sections into a checklist for pull requests, migrations, or architecture reviews.",
        "Use the examples as starting points, then adapt naming, boundaries, and error handling to your codebase.",
        "Share the post with teammates when you need a short, practical explanation of a technical decision.",
      ])}

      <h2>Why this blog exists</h2>
      ${paragraphs([
        "Software portfolios often show finished work but not the thinking behind it. The blog fills that gap by explaining the engineering decisions, mistakes, and patterns that shape real products.",
        "The writing also supports discoverability. Search engines and answer engines need more than a title and a date; they need topic coverage, related terms, and enough natural language to understand why a page is useful.",
        "For readers, the best outcome is simple: leave with a clearer way to build, debug, review, or explain a technical choice. If a post helps a team avoid one fragile abstraction, one rebuild problem, one unclear charging state, or one painful migration, it has done its job.",
      ])}
    </section>
  `;
}

function injectBeforeMainClose(html, addition) {
  if (html.includes('id="extension-guide"') || html.includes('id="vscode-extension-guide"')) {
    return html;
  }
  return html.includes("</main>")
    ? html.replace("</main>", `${addition}\n</main>`)
    : html.replace("</body>", `${addition}\n</body>`);
}

export async function enrichVscodePages(distDir) {
  const hubPath = path.join(distDir, "vscode", "index.html");
  const hubHtml = await readFile(hubPath, "utf8");
  await writeFile(hubPath, injectBeforeMainClose(hubHtml, hubArticle()));

  await Promise.all(
    Object.entries(EXTENSIONS).map(async ([slug, ext]) => {
      const filePath = path.join(distDir, "vscode", slug, "index.html");
      const html = await readFile(filePath, "utf8");
      await writeFile(filePath, injectBeforeMainClose(html, extensionArticle(slug, ext)));
    }),
  );

  const blogPath = path.join(distDir, "blog", "index.html");
  const blogHtml = await readFile(blogPath, "utf8");
  await writeFile(blogPath, injectBeforeMainClose(blogHtml, blogHubArticle()));
}
