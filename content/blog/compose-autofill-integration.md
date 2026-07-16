---
title: "Autofill Support in Jetpack Compose"
slug: "compose-autofill-integration"
description: "Wire Jetpack Compose text fields into Android Autofill Framework for passwords, addresses, and payment data using AutofillNode and semantics."
datePublished: "2025-03-22"
dateModified: "2025-03-22"
tags: ["Android", "Compose"]
keywords: "Compose autofill, AutofillNode, Android autofill framework, password autofill, semantics autofill"
faq:
  - q: "Does OutlinedTextField support autofill automatically?"
    a: "BasicTextField and Material TextField components expose autofill hints through modifier semantics when you set appropriate AutofillType values. You must also register an AutofillNode in a DisposableEffect and connect it to the focus and bounds of the field. Without AutofillNode setup, the system may not offer saved credentials or addresses."
  - q: "How do I autofill passwords in Compose?"
    a: "Set autofill types to listOf(AutofillType.Password) or AutofillType.NewPassword for signup flows. Use passwordVisualTransformation and disable autofill on confirmation fields with AutofillType.Password only on the primary field. Link to Credential Manager for passkeys alongside traditional autofill where supported."
  - q: "Why is autofill not appearing on my Compose screen?"
    a: "Common causes: missing AutofillNode registration, zero-size bounds before layout, disabled autofill on parent composable, or the device autofill service not configured. Verify with Layout Inspector that semantics include autofill types and that onFocusChanged triggers autofill.requestAutofillForNode."
---

Users expect login screens to offer saved passwords. On Compose, that expectation is easy to miss—`OutlinedTextField` looks like a text field but the Autofill Framework does not automatically discover it the way it does for XML `EditText` with `android:autofillHints`. You wire autofill explicitly through semantics, focus callbacks, and `AutofillNode`. Once set up, the pattern copies across every form in your app.

## Autofill building blocks

Android's Autofill Framework needs three things from your UI:

1. **Autofill type hints** — password, username, email, postal address components
2. **Bounds** — screen rectangle of the field when focused
3. **Autofill tree node** — registered with `AutofillManager`

Compose exposes this via `Modifier.semantics` and the `AutofillNode` API in `androidx.compose.ui.platform`.

## Basic password field pattern

```kotlin
@Composable
fun PasswordField(
    value: String,
    onValueChange: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    val autofill = LocalAutofill.current
    val autofillTree = LocalAutofillTree.current
    val focusRequester = remember { FocusRequester() }

    val autofillNode = remember {
        AutofillNode(
            autofillTypes = listOf(AutofillType.Password),
            onFill = { filled -> onValueChange(filled.text) },
        )
    }

    DisposableEffect(autofillNode) {
        autofillTree += autofillNode
        onDispose { autofillTree -= autofillNode }
    }

    BasicTextField(
        value = value,
        onValueChange = onValueChange,
        modifier = modifier
            .focusRequester(focusRequester)
            .onGloballyPositioned { coordinates ->
                autofillNode.boundingBox = coordinates.boundsInWindow()
            }
            .onFocusChanged { focusState ->
                autofill?.run {
                    if (focusState.isFocused) {
                        requestAutofillForNode(autofillNode)
                    } else {
                        cancelAutofillForNode(autofillNode)
                    }
                }
            }
            .semantics {
                contentType = ContentType.Password
            },
        visualTransformation = PasswordVisualTransformation(),
    )
}
```

`ContentType` (Android 15+ / Compose UI 1.8+) aligns with platform autofill hints and improves Credential Manager integration. On older APIs, `AutofillType` on the node remains the primary signal.

## Login form with username and password

Register separate nodes with distinct types:

```kotlin
val usernameNode = remember {
    AutofillNode(
        autofillTypes = listOf(AutofillType.Username),
        onFill = { onUsernameChange(it.text) },
    )
}
val passwordNode = remember {
    AutofillNode(
        autofillTypes = listOf(AutofillType.Password),
        onFill = { onPasswordChange(it.text) },
    )
}
```

Important: important-for-autofill on the window must not be `NO` for the activity. In `Activity.onCreate`:

```kotlin
window.decorView.importantForAutofill =
    View.IMPORTANT_FOR_AUTOFILL_YES
```

For Compose-only activities, set this once in your base activity class.

## Address and payment autofill

Use granular types for address forms—autofill services map saved profiles better:

```kotlin
AutofillType.PostalAddress
AutofillType.PostalCode
AutofillType.CreditCardNumber
AutofillType.CreditCardExpirationDate
```

Split street, city, and zip into separate fields with matching types rather than one multiline field with a generic hint.

## Credential Manager alongside autofill

For passkeys and modern sign-in, integrate Credential Manager in the same screen:

```kotlin
val credentialManager = CredentialManager.create(context)
// GetCredentialRequest with GetPasswordOption + GetPublicKeyCredentialOption
```

Autofill handles saved passwords in the keyboard dropdown; Credential Manager handles passkeys and provider selection. Both can coexist—trigger Credential Manager from a "Sign in with passkey" button, autofill from field focus.

## Testing autofill

Use the Android Emulator with Google autofill or a test autofill service. Steps:

1. Save credentials in Chrome or Settings → Passwords
2. Focus the Compose field—dropdown should appear
3. Verify `onFill` updates state and triggers recomposition

For UI tests, autofill is system-dependent—assert semantics `contentType` and focus behavior rather than the system dropdown.

## Pitfalls

**Bounds zero before first layout.** `onGloballyPositioned` must run before focus; avoid requesting autofill in `LaunchedEffect(Unit)` before layout completes.

**Single AutofillNode for combined fields.** One node per logical autofill target.

**Secure fields in screenshots.** `Modifier.semantics { isSensitive = true }` on OTP and password fields blocks screen capture on supported devices.

**WebView hybrid screens.** Autofill does not cross Compose/WebView boundaries—keep auth flows consistently native or consistently WebView.

## AutofillNode setup for Compose forms

Register autofill semantics on each field:

```kotlin
@Composable
fun LoginForm(viewModel: LoginViewModel) {
    val autofill = LocalAutofill.current
    val autofillTree = LocalAutofillTree.current

    val emailNode = remember {
        AutofillNode(
            autofillTypes = listOf(AutofillType.EmailAddress),
            onFill = { viewModel.email = it.text },
        )
    }
    val passwordNode = remember {
        AutofillNode(
            autofillTypes = listOf(AutofillType.Password),
            onFill = { viewModel.password = it.text },
        )
    }

    LaunchedEffect(autofillTree) {
        autofillTree += emailNode
        autofillTree += passwordNode
    }

    BasicTextField(
        value = viewModel.email,
        onValueChange = { viewModel.email = it },
        modifier = Modifier
            .onGloballyPositioned { emailNode.boundingBox = it.boundsInWindow() }
            .onFocusChanged { if (it.isFocused) autofill?.requestAutofillForNode(emailNode) },
    )
}
```

Each field needs: `AutofillNode` with type, `onGloballyPositioned` for bounds, `onFocusChanged` to trigger autofill request.

## AutofillType mapping

Map fields to correct autofill types for provider recognition:

```kotlin
// Login
AutofillType.EmailAddress
AutofillType.Password

// Registration
AutofillType.NewUsername
AutofillType.NewPassword

// Payment
AutofillType.CreditCardNumber
AutofillType.CreditCardExpirationDate
AutofillType.CreditCardSecurityCode

// Address
AutofillType.PostalAddress
AutofillType.PostalCode
AutofillType.PhoneNumber
```

Incorrect type mapping — password manager saves email in wrong field. Use `NewPassword` for registration, `Password` for login.

## Multi-field autofill (address forms)

Group related fields for single autofill action:

```kotlin
val addressNodes = listOf(streetNode, cityNode, zipNode, countryNode)
addressNodes.forEach { node ->
    node.autofillTypes = listOf(AutofillType.PostalAddress)
}
// All nodes share PostalAddress type — provider fills all at once
```

Provider recognizes address group and fills all fields in one action. Without grouping, user must autofill each field separately.

## Failure modes

- **Autofill requested before layout** — bounds zero; dropdown doesn't appear
- **Wrong AutofillType** — password manager saves to wrong field
- **Missing onGloballyPositioned** — autofill service can't locate field
- **WebView/Compose mixed auth flow** — autofill doesn't cross boundaries
- **Secure field not marked sensitive** — password visible in screenshots

## Production checklist

- AutofillNode registered for every fillable field
- Correct AutofillType per field (NewPassword vs Password)
- onGloballyPositioned sets boundingBox before focus
- Autofill triggered on focus, not on LaunchedEffect(Unit)
- Secure fields marked `isSensitive = true` in semantics
- Auth flow consistently native Compose (no WebView mixing)

## Common production mistakes

Teams get autofill integration wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Compose UI work on autofill integration janks when recomposition scope is too wide, `remember` keys omit stable inputs, and semantics for TalkBack are added only after QA finds focus traps.

## Resources

- [Android Autofill Framework overview](https://developer.android.com/guide/topics/text/autofill)
- [Compose AutofillNode API](https://developer.android.com/reference/kotlin/androidx/compose/ui/platform/AutofillNode)
- [ContentType semantics](https://developer.android.com/reference/kotlin/androidx/compose/ui/autofill/ContentType)
- [Credential Manager guide](https://developer.android.com/training/sign-in/passkeys)
