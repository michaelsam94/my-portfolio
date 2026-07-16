---
title: "Form-Associated Custom Elements"
slug: "web-components-form-association"
description: "Build web components that participate in HTML forms: formAssociated, ElementInternals, setFormValue, validation, and replacing hidden inputs with proper form integration."
datePublished: "2026-03-17"
dateModified: "2026-03-17"
tags: ["Web", "Web Components", "Forms", "Frontend"]
keywords: "form-associated custom elements, ElementInternals, setFormValue, form participation, web components forms"
faq:
  - q: "What are form-associated custom elements?"
    a: "Form-associated custom elements are web components that participate in HTML form submission, validation, and reset as if they were native form controls. Enabled by setting static formAssociated = true on the custom element class, they can expose a value via ElementInternals.setFormValue(), report validity with checkValidity(), and appear in FormData on submit. Before this API, custom form controls required hidden input hacks to participate in forms."
  - q: "How do I set a value on a form-associated custom element?"
    a: "Use the ElementInternals interface obtained via this.attachInternals() in the constructor. Call this.internals.setFormValue(value) whenever the component's value changes. For compound values, pass a FormData object. The browser includes this value in form submission under the element's name attribute, just like a native input. You can also call setFormValue with a second argument for the value presented to accessibility APIs."
  - q: "Can form-associated custom elements use built-in validation?"
    a: "Yes. ElementInternals provides setValidity() to report custom validation errors, checkValidity() to test validity, and the valid attribute is exposed to CSS via :state(valid) and :state(invalid) pseudo-classes. The element participates in the form's constraint validation API, meaning form.checkValidity() will report errors on custom elements and form submission will be blocked if they are invalid, identical to native controls."
---

Before form-associated custom elements, every custom slider, date picker, and rich text editor in a web component needed a hidden `<input>` synced via JavaScript to participate in form submission. I've seen this pattern in dozens of codebases — a shadow DOM widget with a hidden input duct-taped behind it, values synced on every change event, validation duplicated in two places. The `formAssociated` API makes that hack unnecessary. Custom elements can now be first-class form citizens with values, validation, and reset behavior built into the platform.

## Enabling form association

```javascript
class StarRating extends HTMLElement {
  static formAssociated = true;

  constructor() {
    super();
    this._internals = this.attachInternals();
    this._value = 0;
  }

  get value() { return this._value; }
  set value(v) {
    this._value = v;
    this._internals.setFormValue(String(v));
    this._render();
  }

  get name() { return this.getAttribute('name') ?? ''; }
  set name(n) { this.setAttribute('name', n); }
}

customElements.define('star-rating', StarRating);
```

```html
<form id="review">
  <star-rating name="rating" value="3"></star-rating>
  <button type="submit">Submit</button>
</form>
```

On submit, `FormData` includes `rating: "3"` — no hidden inputs.

## ElementInternals API

The key methods:

| Method | Purpose |
|---|---|
| `setFormValue(value, state?)` | Set the submitted value |
| `setValidity(flags, message?, anchor?)` | Report validation state |
| `checkValidity()` | Returns true if valid |
| `reportValidity()` | Show validation message, return validity |
| `form` | The associated form element |
| `labels` | Associated label elements |
| `validationMessage` | Current error message |

## Validation integration

```javascript
class EmailTagInput extends HTMLElement {
  static formAssociated = true;

  constructor() {
    super();
    this._internals = this.attachInternals();
    this._tags = [];
  }

  _validate() {
    if (this._tags.length === 0) {
      this._internals.setValidity(
        { valueMissing: true },
        'Add at least one email tag',
        this
      );
    } else if (this._tags.some(t => !t.includes('@'))) {
      this._internals.setValidity(
        { customError: true },
        'All tags must be valid email addresses',
        this
      );
    } else {
      this._internals.setValidity({});
    }
  }

  addTag(tag) {
    this._tags.push(tag);
    this._internals.setFormValue(this._tags.join(','));
    this._validate();
    this._render();
  }
}
```

```html
<form>
  <email-tag-input name="recipients" required></email-tag-input>
  <button type="submit">Send</button>
</form>
```

`form.checkValidity()` includes the custom element. Submit is blocked if tags are empty or invalid.

## CSS styling by validation state

Form-associated elements expose state via CSS custom state pseudo-classes:

```css
star-rating:state(valid) {
  border-color: green;
}

star-rating:state(invalid) {
  border-color: red;
  outline: 2px solid red;
}
```

Set states in JavaScript:

```javascript
this._internals.states.add('invalid');
this._internals.states.delete('valid');
```

## Compound values with FormData

For components with multiple values:

```javascript
class AddressInput extends HTMLElement {
  static formAssociated = true;

  constructor() {
    super();
    this._internals = this.attachInternals();
  }

  _updateValue() {
    const fd = new FormData();
    fd.set('street', this._street);
    fd.set('city', this._city);
    fd.set('zip', this._zip);
    this._internals.setFormValue(fd);
  }
}
```

On submit, the form receives `street`, `city`, and `zip` as separate entries.

## Form lifecycle events

Form-associated elements receive lifecycle callbacks:

```javascript
class MyControl extends HTMLElement {
  static formAssociated = true;

  formAssociatedCallback(form) {
    // Called when associated with a form
    console.log('Associated with', form.id);
  }

  formDisabledCallback(disabled) {
    // Called when form is disabled or element is disabled
    this.toggleAttribute('disabled', disabled);
  }

  formResetCallback() {
    // Called on form reset — restore default value
    this.value = this.getAttribute('value') ?? '';
  }

  formStateRestoreCallback(state, mode) {
    // Called when browser restores form state (back-forward cache)
    this.value = state;
  }
}
```

`formResetCallback` is critical — without it, custom elements don't reset when the user clicks a reset button.

## Label association

Form-associated elements work with `<label>`:

```html
<label for="rating">Your rating</label>
<star-rating id="rating" name="rating"></star-rating>
```

`this._internals.labels` returns associated labels. Clicking the label focuses the custom element (if it implements `focus()`).

## Browser support

Form-associated custom elements are supported in Chrome 77+, Firefox 93+, Safari 16.4+, and Edge 79+. Check current support at caniuse.com. For older browsers, the hidden-input fallback still works as a progressive enhancement.

## Validation and constraint validation API

Form-associated elements participate in native validation:

```javascript
class DatePicker extends HTMLElement {
  static formAssociated = true;

  checkValidity() {
    if (this.required && !this.value) return false;
    if (this.min && this.value < this.min) return false;
    return true;
  }

  reportValidity() {
    if (!this.checkValidity()) {
      this._internals.setValidity({ customError: true }, 'Invalid date');
      return false;
    }
    this._internals.setValidity({});
    return true;
  }
}
```

Use `ElementInternals.setValidity()` for custom error messages — they appear in native `form.reportValidity()` flows alongside built-in inputs.

## Shadow DOM and form participation

Form-associated elements work inside Shadow DOM — the form element in light DOM still receives values. Critical for design system components:

```html
<form id="checkout">
  <ui-text-input name="email"></ui-text-input>  <!-- shadow DOM inside -->
  <ui-credit-card name="card"></ui-credit-card>
</form>
```

Test `formdata` event and `requestSubmit()` — programmatic submit must include custom element values.

## Progressive enhancement fallback

For Safari < 16.4 and legacy browsers:

```javascript
connectedCallback() {
  if (!('formAssociated' in HTMLElement.prototype)) {
    this._fallbackInput = document.createElement('input');
    this._fallbackInput.type = 'hidden';
    this._fallbackInput.name = this.getAttribute('name');
    this.appendChild(this._fallbackInput);
  }
}
```

Sync hidden input on every value change. Remove fallback when browser support reaches your threshold.

Pair with [CSS nesting native patterns](https://blog.michaelsam94.com/css-nesting-native/) when styling form components within component-scoped stylesheets.

## Common production mistakes

Teams get components form association wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of components form association fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [MDN form-associated custom elements](https://developer.mozilla.org/en-US/docs/Web/API/Web_components/Using_custom_elements#form-associated_custom_elements)
- [ElementInternals specification](https://html.spec.whatwg.org/multipage/custom-elements.html#the-elementinternals-interface)
- [Chrome form-associated CE explainer](https://web.dev/articles/more-capable-form-controls)
- [Can I use form-associated custom elements](https://caniuse.com/mdn-api_elementinternals)
- [web.dev custom form controls](https://web.dev/articles/custom-form-controls)
