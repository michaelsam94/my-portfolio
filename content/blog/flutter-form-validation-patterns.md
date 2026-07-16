---
title: "Form Validation Patterns in Flutter"
slug: "flutter-form-validation-patterns"
description: "Validate Flutter forms correctly: FormState, TextFormField validators, reactive validation with Cubit, async remote checks, and accessible error display."
datePublished: "2024-11-12"
dateModified: "2024-11-12"
tags: ["Flutter", "Dart"]
keywords: "Flutter form validation, TextFormField validator, FormState Flutter, reactive forms Flutter, async validation"
faq:
  - q: "How does Form validation work in Flutter?"
    a: "Wrap inputs in a Form widget with a GlobalKey<FormState>. Each TextFormField accepts a validator returning null for valid or a String error message. Call formKey.currentState!.validate() on submit to run all validators and block submission if any fail. FormState also supports save() for onSaved callbacks."
  - q: "How do I validate forms without setState?"
    a: "Use reactive state management—Cubit, Riverpod, or flutter_form_builder—to hold field values and validation errors as state. Validators run on change or blur; UI rebuilds from state stream. This scales better than GlobalKey for multi-step wizards and cross-field validation."
  - q: "How do I handle async validation like username availability?"
    a: "Debounce input, call API from Cubit or validator returning Future<String?>, show loading indicator on field during check. Prevent form submit while async validation pending. Cache recent results to avoid duplicate requests when user toggles focus."
---

The signup form accepted `@` in passwords because someone copy-pasted a validator that only checked length. Form validation in Flutter isn't hard—`FormState` and `validator` callbacks handle 80% of cases—but the remaining 20% (async checks, cross-field rules, accessibility) separates polished apps from frustrating ones. I've standardized on a few patterns that cover login, checkout, and multi-step onboarding without reinventing validation each feature.

## Basic Form and TextFormField

```dart
class LoginForm extends StatefulWidget {
  @override
  State<LoginForm> createState() => _LoginFormState();
}

class _LoginFormState extends State<LoginForm> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  void _submit() {
    if (!_formKey.currentState!.validate()) return;
    _formKey.currentState!.save();
    // proceed with login
  }

  @override
  Widget build(BuildContext context) {
    return Form(
      key: _formKey,
      autovalidateMode: AutovalidateMode.onUserInteraction,
      child: Column(
        children: [
          TextFormField(
            controller: _emailController,
            decoration: const InputDecoration(labelText: 'Email'),
            keyboardType: TextInputType.emailAddress,
            validator: _validateEmail,
          ),
          TextFormField(
            controller: _passwordController,
            decoration: const InputDecoration(labelText: 'Password'),
            obscureText: true,
            validator: _validatePassword,
          ),
          FilledButton(onPressed: _submit, child: const Text('Sign in')),
        ],
      ),
    );
  }

  String? _validateEmail(String? value) {
    if (value == null || value.isEmpty) return 'Email is required';
    final emailRegex = RegExp(r'^[\w-\.]+@([\w-]+\.)+[\w-]{2,4}$');
    if (!emailRegex.hasMatch(value)) return 'Enter a valid email';
    return null;
  }

  String? _validatePassword(String? value) {
    if (value == null || value.length < 8) {
      return 'Password must be at least 8 characters';
    }
    return null;
  }
}
```

`AutovalidateMode.onUserInteraction` shows errors after first submit attempt without nagging on every keystroke initially.

## Reusable validators

Extract to `lib/core/validation/validators.dart`:

```dart
typedef Validator = String? Function(String?);

Validator required(String fieldName) => (value) {
  if (value == null || value.trim().isEmpty) {
    return '$fieldName is required';
  }
  return null;
};

Validator compose(List<Validator> validators) => (value) {
  for (final v in validators) {
    final error = v(value);
    if (error != null) return error;
  }
  return null;
};

// Usage
validator: compose([required('Email'), _validateEmailFormat]),
```

## Cross-field validation

Confirm password must match:

```dart
String? _validateConfirmPassword(String? value) {
  if (value != _passwordController.text) {
    return 'Passwords do not match';
  }
  return null;
}
```

Or validate at form level:

```dart
bool _validateForm() {
  final valid = _formKey.currentState!.validate();
  if (_passwordController.text != _confirmController.text) {
    setState(() => _confirmError = 'Passwords do not match');
    return false;
  }
  return valid;
}
```

Reactive approach—Cubit holds both values and derives confirm error in state—scales cleaner for complex forms.

## Reactive validation with Cubit

```dart
class SignupState {
  final String email;
  final String? emailError;
  final bool isSubmitting;
  const SignupState({this.email = '', this.emailError, this.isSubmitting = false});

  bool get isValid => emailError == null && email.isNotEmpty;
}

class SignupCubit extends Cubit<SignupState> {
  SignupCubit() : super(const SignupState());

  void emailChanged(String value) {
    emit(state.copyWith(
      email: value,
      emailError: _validateEmail(value),
    ));
  }

  String? _validateEmail(String value) {
    if (value.isEmpty) return 'Email is required';
    if (!emailRegex.hasMatch(value)) return 'Invalid email';
    return null;
  }

  Future<void> submit() async {
    if (!state.isValid) return;
    emit(state.copyWith(isSubmitting: true));
    // ...
  }
}
```

Widget binds to state errors on `InputDecoration.errorText`.

## Async validation

Username availability check:

```dart
class UsernameCubit extends Cubit<UsernameState> {
  UsernameCubit(this._api) : super(const UsernameState());
  final UserApi _api;
  Timer? _debounce;

  void usernameChanged(String value) {
    _debounce?.cancel();
    emit(state.copyWith(username: value, status: ValidationStatus.checking));
    _debounce = Timer(const Duration(milliseconds: 400), () => _check(value));
  }

  Future<void> _check(String username) async {
    if (username.length < 3) {
      emit(state.copyWith(status: ValidationStatus.invalid, error: 'Too short'));
      return;
    }
    try {
      final available = await _api.isUsernameAvailable(username);
      emit(state.copyWith(
        status: available ? ValidationStatus.valid : ValidationStatus.invalid,
        error: available ? null : 'Username taken',
      ));
    } catch (_) {
      emit(state.copyWith(status: ValidationStatus.error, error: 'Could not verify'));
    }
  }
}
```

Show `suffixIcon: CircularProgressIndicator` while `checking`. Disable submit until `valid`.

## Accessibility

- Link errors to fields via `Semantics` or ensure `errorText` is announced—Material fields do this automatically.
- Focus first invalid field on failed submit:

```dart
if (!_formKey.currentState!.validate()) {
  FocusScope.of(context).requestFocus(_emailFocusNode);
  return;
}
```

- Don't rely on color alone—include error text always.

### Packages when forms grow large

- **flutter_form_builder** — declarative field definitions, built-in validators.
- **reactive_forms** — Angular-style reactive forms for Dart.
- **formz** — validated input models per field, pairs well with Cubit.

For simple login, stick with `Form` + validators. Adopt packages when you have 15+ fields or dynamic field lists.

### AutovalidateMode strategy

Use `AutovalidateMode.disabled` until first submit attempt, then switch to `onUserInteraction`:

```dart
AutovalidateMode _mode = AutovalidateMode.disabled;

void _submit() {
  setState(() => _mode = AutovalidateMode.onUserInteraction);
  if (!_formKey.currentState!.validate()) return;
}
```

Reduces aggressive error display on first keystroke while keeping post-submit responsiveness users expect from native forms.

Password strength meters belong in UI layer with zxcvbn or similar—don't block submit on weak password without explaining rules inline. Server-side validation always wins; client validation reduces round trips and improves UX but never replaces API validation for security fields.

Production teams should treat this guidance as living documentation: revisit assumptions after major platform upgrades, measure outcomes with real metrics rather than checklist compliance, and pair written standards with automated checks in CI. The patterns here reflect what held up in shipped apps—not theoretical perfection. Adapt thresholds, timeouts, and tooling to your stack, but keep the underlying principles: explicit configuration, testable behavior, and failure modes users can understand.

When onboarding new engineers, walk through one end-to-end example in a debug build before asking them to extend the pattern. Most failures I have seen came from skipped platform setup steps—manifest entries, API keys, code generation, or permission prompts—not from misunderstanding the Dart layer. Keep a troubleshooting section in your team wiki linking official docs and the exact commands that worked for your last upgrade.

## Resources

- [Form class API](https://api.flutter.dev/flutter/widgets/Form-class.html)
- [TextFormField validator](https://api.flutter.dev/flutter/material/TextFormField-class.html)
- [formz package](https://pub.dev/packages/formz)
- [flutter_form_builder](https://pub.dev/packages/flutter_form_builder)
- [Flutter input validation cookbook](https://docs.flutter.dev/cookbook/forms/validation)
