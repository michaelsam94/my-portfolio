---
title: "The New Compose TextField State APIs"
slug: "compose-text-field-state-2026"
description: "Migrate to Compose TextFieldState and TextFieldBuffer for efficient text input, undo/redo, output transformation, and state observation in 2025+ APIs."
datePublished: "2025-04-18"
dateModified: "2025-04-18"
tags: ["Android", "Compose"]
keywords: "TextFieldState, Compose TextField 2025, TextFieldBuffer, BasicTextField state, input transformation"
faq:
  - q: "What is TextFieldState in Compose?"
    a: "TextFieldState is a mutable text input state class replacing TextFieldValue for new code. It stores text, selection, and composition in a single observable object with efficient change notifications. It integrates with BasicTextField overloads that accept state directly and supports output transformations for formatting like phone masks without mutating stored text."
  - q: "Should I migrate from TextFieldValue to TextFieldState?"
    a: "New screens should use TextFieldState. Existing TextFieldValue code continues working—migration is incremental. TextFieldState shines with output transformations, undo history, and kotlinx.coroutines Flow observation via snapshotFlow. Material3 TextField adds state-based overloads alongside legacy value/onValueChange."
  - q: "How do output transformations differ from VisualTransformation?"
    a: "VisualTransformation only changes display—the underlying text stays raw. OutputTransformation formats text as users type (adding dashes to phone numbers) while keeping a separate visual representation. InputTransformation validates or filters incoming characters before they enter the buffer."
---

Compose text input spent years on the `TextFieldValue(text, selection, composition)` triplet—fine for basic cases, awkward for formatted input, undo stacks, and observing changes without boxing every keystroke into a new data class. `TextFieldState` and its buffer API are the replacement path Material and Foundation are betting on for new code. If you are building forms in 2025, start here—not another wrapper around `mutableStateOf("")`.

## Basic TextFieldState usage

```kotlin
@Composable
fun EmailField(state: TextFieldState, modifier: Modifier = Modifier) {
    BasicTextField(
        state = state,
        modifier = modifier,
        lineLimits = TextFieldLineLimits.SingleLine,
        inputTransformation = InputTransformation.then(KeyboardOptions(capitalization = KeyboardCapitalization.None)),
    )
}

@Composable
fun SignUpScreen() {
    val emailState = rememberTextFieldState()
    val passwordState = rememberTextFieldState()

    Column {
        EmailField(state = emailState)
        PasswordField(state = passwordState)

        Button(onClick = {
            submit(emailState.text.toString(), passwordState.text.toString())
        }) {
            Text("Sign up")
        }
    }
}
```

`rememberTextFieldState(initialText = "")` survives recomposition; hoist to ViewModel for process death with saved state hooks.

## Observing text changes

```kotlin
val state = rememberTextFieldState()

LaunchedEffect(state) {
    snapshotFlow { state.text.toString() }
        .debounce(300)
        .collect { query -> viewModel.search(query) }
}
```

`snapshotFlow` reads snapshot state efficiently—better than `onValueChange` forwarding for debounced search.

## Output transformation (phone mask)

```kotlin
@OptIn(ExperimentalFoundationApi::class)
fun phoneOutputTransformation(): OutputTransformation {
    return OutputTransformation { buffer ->
        val digits = buffer.text.filter { it.isDigit() }.take(10)
        val formatted = buildString {
            digits.forEachIndexed { i, c ->
                if (i == 3 || i == 6) append('-')
                append(c)
            }
        }
        if (buffer.text.toString() != formatted) {
            buffer.replace(0, buffer.length, formatted)
        }
    }
}

BasicTextField(
    state = state,
    outputTransformation = phoneOutputTransformation(),
    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
)
```

Stored text matches displayed formatted text with output transformation—unlike VisualTransformation which hides formatting from the model.

## Input transformation (validation)

```kotlin
val digitsOnly = InputTransformation { _, proposed ->
    proposed.filter { it.isDigit() }
}

BasicTextField(state = state, inputTransformation = digitsOnly)
```

Reject characters before they enter state—cleaner than fixing text in `onValueChange` after the fact.

## Material3 TextField integration

```kotlin
OutlinedTextField(
    state = emailState,
    label = { Text("Email") },
    modifier = Modifier.fillMaxWidth(),
)
```

Material wrappers pass through to state-based BasicTextField internally in recent Material3 versions.

## Hoisting to ViewModel

```kotlin
class EditProfileViewModel : ViewModel() {
    val nameState = TextFieldState(initialText = "")
    val bioState = TextFieldState(initialText = "")

    fun load(profile: Profile) {
        nameState.edit { replace(0, length, profile.name) }
        bioState.edit { replace(0, length, profile.bio) }
    }
}
```

Use `TextFieldState.edit { }` batch mutations for atomic buffer updates with single notification.

## Undo/redo

TextFieldState maintains undo history when edits go through the buffer API:

```kotlin
IconButton(onClick = { state.undo() }) {
    Icon(Icons.AutoMirrored.Filled.Undo, "Undo")
}
```

Programmatic `state.edit` calls can merge into undo stack with appropriate flags—check API version docs for `InputTransformation` undo behavior.

## Migration from TextFieldValue

| TextFieldValue | TextFieldState |
|----------------|----------------|
| `value.copy(text = new)` | `state.edit { replace(...) }` |
| `onValueChange = { value = it }` | pass `state` directly |
| `VisualTransformation` | `OutputTransformation` for model sync |
| Selection via `TextRange` | `state.selection` property |

Bridge period—both APIs coexist. Migrate screen by screen.

## Common pitfalls

**Reading `state.text` during composition without snapshot subscription.** Use `state.text.toString()` inside TextField or collect via snapshotFlow—direct reads work but trigger recomposition every keystroke (usually intended in the field itself).

**Replacing state instance on config change.** Use rememberSaveable with Saver or hold in ViewModel—do not recreate state losing user input.

**Mixing controlled patterns.** Do not also pass legacy `value`/`onValueChange` with `state`—pick one API surface.

## TextFieldState in ViewModel

Hoist state to ViewModel for form validation and submission:

```kotlin
class LoginViewModel : ViewModel() {
    val emailState = TextFieldState()
    val passwordState = TextFieldState()

    val isValid: StateFlow<Boolean> = snapshotFlow {
        emailState.text.contains("@") && passwordState.text.length >= 8
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), false)

    fun submit() {
        if (!isValid.value) return
        authRepository.login(emailState.text.toString(), passwordState.text.toString())
    }
}
```

TextFieldState survives configuration changes when held in ViewModel — no rememberSaveable needed.

## InputTransformation for formatting

Format input as user types without changing the underlying model:

```kotlin
val phoneState = TextFieldState()

BasicTextField(
    state = phoneState,
    inputTransformation = InputTransformation.byValue { _, proposed ->
        // Allow only digits, max 10
        proposed.filter { it.isDigit() }.take(10)
    },
    outputTransformation = OutputTransformation {
        // Display as (XXX) XXX-XXXX
        val digits = it.text.filter { c -> c.isDigit() }
        if (digits.length >= 6) {
            replace(0, it.length, "(${digits.take(3)}) ${digits.drop(3).take(3)}-${digits.drop(6)}")
        }
    }
)
```

InputTransformation filters/modifies on input. OutputTransformation formats display without changing stored value.

## Accessibility with TextFieldState

TextFieldState integrates with Compose semantics:

```kotlin
OutlinedTextField(
    state = emailState,
    label = { Text("Email") },
    modifier = Modifier.semantics {
        contentDescription = "Email address input"
        if (emailState.text.isEmpty()) {
            error("Email is required")
        }
    }
)
```

Set semantics error state based on validation — TalkBack announces errors on focus. Pair with `isError` parameter for visual error indicator.

## Failure modes

- **Recreating TextFieldState on recomposition** — user input lost; hold in ViewModel
- **Reading state.text without subscription** — stale UI; use inside TextField or snapshotFlow
- **InputTransformation too aggressive** — cursor jumps; test on real devices
- **Mixed controlled APIs** — legacy value/onValueChange + state causes double updates
- **No saveable state for process death** — use rememberSaveable with TextFieldState.Saver

## Production checklist

- TextFieldState held in ViewModel for forms with validation
- InputTransformation for input filtering (digits, max length)
- OutputTransformation for display formatting (phone, currency)
- Semantics error state set on validation failure
- rememberSaveable with Saver for simple single-field cases
- Migrated from TextFieldValue screen by screen

## Common production mistakes

Teams get text field state 2026 wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Compose UI work on text field state 2026 janks when recomposition scope is too wide, `remember` keys omit stable inputs, and semantics for TalkBack are added only after QA finds focus traps.

## Resources

- [TextFieldState reference](https://developer.android.com/reference/kotlin/androidx/compose/foundation/text/input/TextFieldState)
- [BasicTextField state overload](https://developer.android.com/reference/kotlin/androidx/compose/foundation/text/BasicTextField)
- [OutputTransformation guide](https://developer.android.com/jetpack/compose/text/user-input)
- [Material3 OutlinedTextField state](https://developer.android.com/reference/kotlin/androidx/compose/material3/OutlinedTextField)
