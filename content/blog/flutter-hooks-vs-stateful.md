---
title: "Flutter Hooks vs StatefulWidget"
slug: "flutter-hooks-vs-stateful"
description: "Flutter hooks vs StatefulWidget: how flutter_hooks cuts boilerplate, useState and useEffect in practice, the lifecycle mapping, and when each one wins."
datePublished: "2026-03-21"
dateModified: "2026-03-21"
tags: ["Flutter", "Dart", "State Management"]
keywords: "Flutter hooks, flutter_hooks, StatefulWidget, useState, useEffect Flutter, hooks vs stateful"
faq:
  - q: "What are Flutter hooks?"
    a: "Flutter hooks are a set of reusable functions from the flutter_hooks package that let you manage local widget state and lifecycle inside a HookWidget's build method, without writing a separate State class. Inspired by React hooks, they replace the ceremony of StatefulWidget — initState, dispose, and setState — with composable calls like useState, useEffect, and useAnimationController."
  - q: "Are Flutter hooks better than StatefulWidget?"
    a: "Neither is universally better. Hooks dramatically reduce boilerplate and make lifecycle logic reusable across widgets, which shines when you have many controllers or repeated patterns. StatefulWidget is built in, has zero dependencies, and is more explicit, which some teams prefer. Hooks trade a little magic and a learning curve for a lot less code."
  - q: "Can I mix hooks and StatefulWidget in the same app?"
    a: "Yes. flutter_hooks is opt-in per widget — a HookWidget and a StatefulWidget can coexist in the same tree without conflict. Many teams introduce hooks gradually, using them for controller-heavy screens while leaving simple StatefulWidgets untouched. You never have to migrate everything at once."
---

Anyone who's written a Flutter screen with three animation controllers and two text controllers knows the ritual: declare each one as a field, initialize it in `initState`, remember to dispose it in `dispose`, and hope you didn't forget one. Flutter hooks, via the `flutter_hooks` package, collapse that ceremony into single-line calls inside `build`. `useState` gives you reactive local state, `useAnimationController` gives you a controller that disposes itself, and `useEffect` handles setup and teardown together — no separate `State` class, no manual disposal, far less code to get wrong.

I'll be straight about my bias: after enough forgotten `dispose` calls leaking controllers, I lean toward hooks for anything controller-heavy. But `StatefulWidget` isn't going anywhere, and there are real reasons to keep reaching for it. Let's compare them honestly.

## The boilerplate problem hooks solve

Here's a routine `StatefulWidget` that manages a text controller and a focus node:

```dart
class SearchBar extends StatefulWidget {
  const SearchBar({super.key});
  @override
  State<SearchBar> createState() => _SearchBarState();
}

class _SearchBarState extends State<SearchBar> {
  late final TextEditingController _controller;
  late final FocusNode _focus;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController();
    _focus = FocusNode();
  }

  @override
  void dispose() {
    _controller.dispose();
    _focus.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) =>
      TextField(controller: _controller, focusNode: _focus);
}
```

That's roughly 25 lines to manage two disposables. The same widget with hooks:

```dart
class SearchBar extends HookWidget {
  const SearchBar({super.key});
  @override
  Widget build(BuildContext context) {
    final controller = useTextEditingController();
    final focus = useFocusNode();
    return TextField(controller: controller, focusNode: focus);
  }
}
```

The disposal happens automatically — `useTextEditingController` registers its own cleanup. There is no `dispose` to forget because there's no `dispose` at all. Multiply that across a codebase and the reduction is real, not cosmetic.

## useState and useEffect

The two workhorses map onto concepts every Flutter dev already knows. `useState` returns a `ValueNotifier`-like object whose `.value` setter triggers a rebuild — it's `setState` for a single piece of state:

```dart
final count = useState(0);
// ...
ElevatedButton(
  onPressed: () => count.value++,   // rebuilds automatically
  child: Text('${count.value}'),
)
```

`useEffect` combines `initState` and `dispose` into one call. You return an optional cleanup function, and you control when it re-runs via a keys list:

```dart
useEffect(() {
  final sub = stream.listen(handleEvent);
  return sub.cancel;          // cleanup, like dispose
}, [stream]);                 // re-runs only when stream changes
```

That keys list is the sharpest tool and the sharpest edge. An empty `[]` means "run once"; `[stream]` means "re-run when stream changes"; omitting the list means "run every build," which is almost always a bug. Coming from `StatefulWidget`, this dependency-array thinking is the main mental adjustment.

## Lifecycle mapping

For teams migrating, it helps to see the direct translation between the two models:

| StatefulWidget | flutter_hooks | Notes |
|---|---|---|
| `initState` | `useEffect(fn, [])` | Runs once on mount |
| `dispose` | return from `useEffect` | Cleanup function |
| `didUpdateWidget` | `useEffect(fn, [dep])` | Re-run on dependency change |
| `setState` | `useState(...).value =` | Triggers rebuild |
| controller fields | `use*Controller()` | Auto-disposed |

The mapping is clean enough that most `StatefulWidget` patterns have an obvious hook equivalent. What hooks add on top is *composition* — you can extract a group of hooks into a custom hook function and reuse it across widgets, which `StatefulWidget` can't do without inheritance or mixin gymnastics.

## The Rules of Hooks

Hooks come with two non-negotiable rules, and violating them causes subtle, maddening bugs:

1. **Only call hooks at the top level of `build`** — never inside conditionals, loops, or callbacks.
2. **Always call the same hooks in the same order** on every build.

The reason is that hooks are identified by call order, not by name. Wrap a `useState` in an `if` and on some builds the order shifts, so state gets assigned to the wrong hook. This is genuinely the biggest downside: the framework can't fully enforce these rules, so a careless edit introduces a bug that doesn't crash immediately. The `flutter_hooks` lint helps, and I consider it mandatory — do not run hooks without the analyzer rule enabled.

## Where each one wins

Hooks are not a state management solution; they're a local-state and lifecycle tool. They pair with, not against, app-level state. I run hooks for widget-local concerns and [Riverpod for app state](https://blog.michaelsam94.com/flutter-riverpod-state-management/) — which is no accident, since Riverpod comes from the same author and `HookConsumerWidget` merges both cleanly. If you're weighing broader architectures, my comparison of [Riverpod versus BLoC](https://blog.michaelsam94.com/riverpod-vs-bloc-2026/) covers the app-state layer that sits above whatever local approach you choose.

Reach for **hooks** when a widget juggles multiple controllers, when you have repeated lifecycle patterns worth extracting, or when the `initState`/`dispose` boilerplate genuinely dominates the file. Reach for **StatefulWidget** when you want zero dependencies, when the team is uncomfortable with the call-order magic, or when the widget's state is one simple flag where the boilerplate savings are trivial.

One more consideration that decides it for a lot of teams: custom hooks. Because a hook is just a function that calls other hooks, you can extract a recurring pattern — say, a debounced text field that wires a `TextEditingController` to a timer — into a single `useDebouncedText()` and reuse it everywhere. Reproducing that reuse with `StatefulWidget` means a mixin or a wrapper widget, both clunkier. That composability is the feature I'd miss most if I went back, and it's the strongest argument for hooks beyond the raw line-count reduction.

My honest position: for a solo project or a team that'll invest in the Rules of Hooks, `flutter_hooks` removes a category of bugs (leaked controllers) and a lot of noise. For a large team with mixed experience, the implicit call-order contract is a real risk, and plain `StatefulWidget` — verbose but explicit — can be the safer default. Neither answer is wrong; just don't adopt hooks halfway, without the lint, and expect a good time.

## Resources

- [flutter_hooks on pub.dev](https://pub.dev/packages/flutter_hooks)
- [flutter_hooks GitHub repository](https://github.com/rrousselGit/flutter_hooks)
- [Flutter StatefulWidget documentation](https://api.flutter.dev/flutter/widgets/StatefulWidget-class.html)
- [React Rules of Hooks (conceptual origin)](https://react.dev/reference/rules/rules-of-hooks)
- [Flutter state management overview](https://docs.flutter.dev/data-and-backend/state-mgmt/intro)
