---
title: "AI Agents: Focus Trap Modal Dialogs"
slug: "agent-focus-trap-modal-dialogs"
description: "Implement accessible modal focus traps with correct aria-modal semantics, inert backgrounds, escape handling, and nested dialog stacks that survive keyboard and screen reader testing."
datePublished: "2026-06-23"
dateModified: "2026-06-23"
tags: ["AI", "Agent", "Focus"]
keywords: "focus trap, modal dialog, accessibility, aria-modal, inert, keyboard navigation, WCAG"
faq:
  - q: "Should modals always trap focus?"
    a: "Yes for true modal dialogs that block interaction with the page behind them. Non-modal panels, drawers that allow parallel page interaction, and alert dialogs with different semantics need lighter patterns—trapping focus where users can still interact with the background creates confusion."
  - q: "What happens to focus when the modal closes?"
    a: "Return focus to the element that opened the modal, usually the triggering button. If that element was removed from the DOM, move focus to a sensible fallback such as the dialog's container heading or the page main landmark."
  - q: "How do nested modals affect focus order?"
    a: "Each layer pushes onto a focus stack: trap within the topmost dialog, pause the previous trap without releasing background inertness, and pop the stack on close so focus never leaks to the page beneath an still-open parent dialog."
  - q: "Does aria-hidden on the background replace the inert attribute?"
    a: "Not reliably. aria-hidden hides content from the accessibility tree but does not prevent focus from reaching elements via Tab. Prefer inert where supported, supplemented with aria-hidden and careful manual focus guards for older browsers."
---
Modal dialogs are among the most accessibility-audited UI patterns—and among the most commonly broken. A visually centered overlay is not a dialog; a dialog is a contract with assistive technology: `role=\"dialog\"`, an accessible name, `aria-modal=\"true\"`, a focus trap that keeps keyboard users inside, and a restore path that returns focus when the layer dismisses. Agent dashboards, confirmation flows, and AI-generated content previews all rely on modals; when focus escapes to the page beneath, screen reader users hear two contexts at once, and keyboard users tab into a page they cannot see.

This guide explains how to implement focus-trapped modal dialogs that pass axe and manual screen reader testing, handle nested stacks, and avoid the subtle bugs that ship when teams copy a React hook without understanding what it disables underneath.

## Modal semantics: what assistive tech expects

A **modal dialog** blocks interaction with the rest of the page until dismissed. Assistive technologies use these signals:

| Attribute / role | Purpose |
|------------------|---------|
| `role=\"dialog\"` or `<dialog>` | Identifies the window |
| `aria-modal=\"true\"` | Signals that content outside is inactive |
| `aria-labelledby` / `aria-label` | Provides an accessible name |
| Focus inside on open | Context moves into the dialog |
| Inert or equivalent on background | Prevents tab escape and pointer events |

Using `<dialog showModal()>` gives you some browser-native behavior—top layer promotion and backdrop—but you still must manage focus return and test across Safari, Firefox, and Chrome. Many design systems wrap a `<div role=\"dialog\">` for styling control; that is fine if semantics and focus behavior are explicit.

**Alert dialogs** (`role=\"alertdialog\"`) demand immediate attention and often trap focus similarly, but copy and button expectations differ—typically a single primary action. Do not use alertdialog for generic forms.

## The focus trap algorithm

A focus trap listens for `Tab` and `Shift+Tab` at the dialog edges and wraps focus to the opposite end. Implementation steps:

1. Query **focusable elements** inside the dialog: links, buttons, inputs, selects, textareas, elements with `tabindex=\"0\"`, and `[contenteditable]`.
2. Filter out `disabled`, `aria-hidden`, and `tabindex=\"-1\"` elements unless you explicitly manage roving tabindex.
3. On open, move focus to the first focusable element—or the dialog container if you prefer focus on the heading via `tabindex=\"-1\"`.
4. On `keydown Tab` from the last element, focus the first; on `Shift+Tab` from the first, focus the last.
5. On close, restore previously focused element from a saved reference.

```typescript
const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

function getFocusable(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
    (el) => !el.hasAttribute("disabled") && el.offsetParent !== null
  );
}

function trapTabKey(event: KeyboardEvent, container: HTMLElement) {
  if (event.key !== "Tab") return;
  const nodes = getFocusable(container);
  if (nodes.length === 0) {
    event.preventDefault();
    return;
  }
  const first = nodes[0];
  const last = nodes[nodes.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}
```

Avoid trapping only `button` elements—custom comboboxes and rich text editors expose focusable children your selector must include.

## Inert backgrounds and pointer blocking

Trapping keyboard focus is insufficient if users can still click the page behind the overlay. Layer defenses:

- **`inert`** on `#root` siblings or a dedicated `main` wrapper—supported in modern Chromium, Safari, and Firefox
- **`pointer-events: none`** on a full-screen backdrop sibling combined with `pointer-events: auto` on the dialog panel
- **`aria-hidden=\"true\"`** on background regions **after** moving focus into the dialog—never hide an ancestor of focused content

```typescript
function lockBackground(appRoot: HTMLElement) {
  const previous = document.activeElement as HTMLElement | null;
  appRoot.inert = true;
  appRoot.setAttribute("aria-hidden", "true");
  return () => {
    appRoot.inert = false;
    appRoot.removeAttribute("aria-hidden");
    previous?.focus?.();
  };
}
```

When `inert` is unavailable, maintain a **focus guard** sentinel at the start and end of the document that redirects stray tab events back into the dialog—less elegant, but necessary for legacy enterprise browsers on long-tail support contracts.

## Open and close lifecycle

**On open:**

1. Save `document.activeElement`
2. Apply background inertness / aria-hidden
3. Move focus into the dialog
4. Attach `keydown` listener for Tab trap and Escape policy
5. Optionally lock body scroll with `overflow: hidden` and preserve scroll position to avoid layout shift

**On close:**

1. Remove listeners and inertness
2. Restore focus to the saved trigger element
3. If trigger is gone, focus `#main` or the dialog title heading marked `tabindex=\"-1\"`

```tsx
export function Modal({ open, onClose, title, children }: ModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    restoreFocusRef.current = document.activeElement as HTMLElement;
    const root = document.getElementById("app-root");
    const unlock = root ? lockBackground(root) : () => {};
    const node = dialogRef.current;
    const focusables = node ? getFocusable(node) : [];
    (focusables[0] ?? node)?.focus();

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }
      if (node) trapTabKey(e, node);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      unlock();
      restoreFocusRef.current?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="modal-backdrop">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
      >
        <h2 id="modal-title">{title}</h2>
        {children}
      </div>
    </div>
  );
}
```

## Escape key policy

WCAG does not require Escape to close dialogs, but users expect it. Document product policy:

- **Destructive confirmations** — Escape closes without saving (same as Cancel)
- **Unsaved edits** — Escape triggers an inner confirmation or is disabled with visible hint text
- **Non-dismissible flows** — Omit Escape handling but provide an explicit Cancel; rare and should be flagged in QA

Never leave Escape listeners attached after unmount—memory leaks and ghost closes are common in SPA route transitions.

## Nested modals and focus stacks

Opening a second dialog over the first requires a **stack**, not a single global trap:

```typescript
const focusStack: Array<{ restore: () => void; container: HTMLElement }> = [];

function pushModal(container: HTMLElement) {
  const restore = lockBackground(document.getElementById("app-root")!);
  focusStack.push({ restore, container });
}

function popModal() {
  const entry = focusStack.pop();
  entry?.restore();
  const prev = focusStack[focusStack.length - 1];
  if (prev) {
    getFocusable(prev.container)[0]?.focus();
  }
}
```

Only the topmost dialog receives Tab wrapping. Background inertness applies to the full app except the dialog stack—do not remove inert from `#app-root` when closing a child if the parent modal remains open.

## Scroll containment and mobile viewports

iOS Safari historically allowed focus to scroll the background despite overlays. Mitigations:

- `position: fixed` on body during open with stored `scrollY` restore on close
- `overscroll-behavior: contain` on the dialog panel
- Ensure the dialog scrolls internally when content exceeds viewport height—trapped focus must reach overflow controls

Test with on-screen keyboard open; inputs near the bottom of mobile modals often lose visibility without scroll padding.

## Common failure modes in production

| Symptom | Likely cause |
|---------|----------------|
| Focus jumps to URL bar | Missing trap on first Tab from last element |
| Screen reader reads background | `aria-hidden` on ancestor of focused node |
| Double backdrop click closes wrong layer | Shared click handler without stack depth check |
| Focus lost after route change | Trigger unmounted without fallback target |
| axe \"focusable content outside dialog\" | Portals rendering toast outside inert subtree |

Portals (React `createPortal`) should render modals as siblings of `#app-root` or inside a dedicated top-layer container that participates in the same inert lock.

## Testing strategy

Automated:

- `@axe-core/playwright` rules: `aria-dialog-name`, `focus-trap`, `aria-hidden-focus`
- Unit-test `getFocusable` with shadow DOM if your components use web components

Manual (required):

- VoiceOver on macOS Safari: open dialog, VO+arrow through contents, verify background silence
- NVDA on Windows Firefox/Chrome: Tab and Shift+Tab wrap correctly
- Zoom 400%: dialog remains scrollable and focus visible

Record short screen captures of failing builds—regressions often arrive with design system token refactors that change `display: none` on focusable chips.

## Integration with AI agent UIs

Agent products frequently stream partial results into confirmation modals (\"Apply this diff?\"). Dynamic content insertion can **shift focusable order** mid-session. When new buttons mount after streaming completes, avoid stealing focus from the textarea unless the new control is the primary action—announce updates via `aria-live=\"polite\"` on a status region instead.

For tool-call approval flows, bind modal open to explicit user gestures where possible; programmatic opens from websocket events should still move focus and trap immediately, with a visible banner explaining why the dialog appeared.

## The takeaway

Focus-trapped modals are accessibility infrastructure, not CSS exercises. Combine correct ARIA, inert backgrounds, a tested Tab wrap algorithm, and a focus restoration stack for nested layers. Validate with automated axe checks and manual screen reader passes on every design system release. Users who navigate by keyboard or voice should experience one clear context at a time—no exceptions for AI-generated urgency.

## Resources

- [WAI-ARIA Authoring Practices — Modal Dialog Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/)
- [WCAG 2.2 — Focus Not Obscured](https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html)
- [HTML `<dialog>` element — MDN](https://developer.mozilla.org/en-US/docs/Web/HTML/Element/dialog)
- [inert attribute — MDN](https://developer.mozilla.org/en-US/docs/Web/HTML/Global_attributes/inert)
- [focus-trap library (reference implementation)](https://github.com/focus-trap/focus-trap)
- [Deque axe rules — aria-dialog-name](https://dequeuniversity.com/rules/axe/4.9/aria-dialog-name)
