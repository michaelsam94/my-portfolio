function inline(text: string) {
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g);
  return parts.map((part, index) => {
    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={index}>{part.slice(1, -1)}</code>;
    }
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    return part;
  });
}

function flushParagraph(lines: string[], nodes: React.ReactNode[]) {
  if (!lines.length) return;
  nodes.push(<p key={`p-${nodes.length}`}>{inline(lines.join(" "))}</p>);
  lines.length = 0;
}

export function renderMarkdown(markdown: string) {
  const nodes: React.ReactNode[] = [];
  const paragraph: string[] = [];
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    if (!trimmed) {
      flushParagraph(paragraph, nodes);
      i += 1;
      continue;
    }

    if (trimmed.startsWith("```")) {
      flushParagraph(paragraph, nodes);
      const code: string[] = [];
      i += 1;
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        code.push(lines[i]);
        i += 1;
      }
      nodes.push(
        <pre key={`pre-${nodes.length}`}>
          <code>{code.join("\n")}</code>
        </pre>,
      );
      i += 1;
      continue;
    }

    if (trimmed.startsWith("## ")) {
      flushParagraph(paragraph, nodes);
      nodes.push(<h2 key={`h2-${nodes.length}`}>{inline(trimmed.slice(3))}</h2>);
      i += 1;
      continue;
    }

    if (trimmed.startsWith("### ")) {
      flushParagraph(paragraph, nodes);
      nodes.push(<h3 key={`h3-${nodes.length}`}>{inline(trimmed.slice(4))}</h3>);
      i += 1;
      continue;
    }

    if (/^[-*]\s+/.test(trimmed)) {
      flushParagraph(paragraph, nodes);
      const items: string[] = [];
      while (i < lines.length && /^[-*]\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^[-*]\s+/, ""));
        i += 1;
      }
      nodes.push(
        <ul key={`ul-${nodes.length}`}>
          {items.map((item) => (
            <li key={item}>{inline(item)}</li>
          ))}
        </ul>,
      );
      continue;
    }

    if (trimmed.startsWith("|")) {
      flushParagraph(paragraph, nodes);
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        const cells = lines[i]
          .trim()
          .replace(/^\||\|$/g, "")
          .split("|")
          .map((cell) => cell.trim());
        if (!cells.every((cell) => /^:?-{3,}:?$/.test(cell))) rows.push(cells);
        i += 1;
      }
      const [head, ...body] = rows;
      nodes.push(
        <table key={`table-${nodes.length}`}>
          {head ? (
            <thead>
              <tr>{head.map((cell) => <th key={cell}>{inline(cell)}</th>)}</tr>
            </thead>
          ) : null}
          <tbody>
            {body.map((row, rowIndex) => (
              <tr key={rowIndex}>
                {row.map((cell, cellIndex) => (
                  <td key={`${rowIndex}-${cellIndex}`}>{inline(cell)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>,
      );
      continue;
    }

    paragraph.push(trimmed);
    i += 1;
  }

  flushParagraph(paragraph, nodes);
  return nodes;
}
