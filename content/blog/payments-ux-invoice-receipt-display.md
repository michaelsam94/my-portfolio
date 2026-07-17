---
title: "Invoice and Receipt Display Patterns"
slug: "payments-ux-invoice-receipt-display"
description: "Post-purchase receipt UX — PDF download, email resend, tax line items, and accessible invoice tables."
datePublished: "2026-11-06"
dateModified: "2026-07-17"
tags: ["Payments", "UX", "Billing"]
keywords: "invoice receipt UX, billing history UI, payment confirmation page"
faq:
  - q: "What must a receipt show for B2C vs B2B?"
    a: "B2C: merchant name, date, amount, last4, support contact. B2B: legal entity, VAT ID, line items with tax breakdown, invoice number sequential per jurisdiction."
  - q: "Should receipts be emailed and in-app?"
    a: "Both — email is proof for expense reports; in-app is immediate confirmation. Same template content; PDF attachment for B2B with embedded fonts for print."
  - q: "How do refunds appear on receipts?"
    a: "Original charge plus separate refund line with linked reference — not silent net amount. Users reconciling cards need gross charge visibility."

---

Receipts are post-purchase UX — users screenshot them for expenses, support uses them to answer "was I charged?", and finance needs VAT-compliant PDFs. Treat receipts as product surface, not email afterthought.

## Receipt hierarchy

Amount paid is hero typography. Below: date/time, payment method last4, merchant descriptor, line items (collapsible), tax breakdown, support link, PDF download. Users reimburse from screenshot of top third only — optimize that band.

## B2C vs B2B templates

B2C: merchant name, amount, date, last4. B2B: sequential invoice number, legal entity, buyer VAT ID, per-line tax rates, payment terms. Branch templates on `invoice.billing_reason`.

## VAT and multi-jurisdiction

EU B2C digital services charge customer-country VAT — show rate and amount per line. US: sales tax line when nexus applies; "Tax calculated at checkout" on preview, exact on final receipt.

## Refunds on receipts

Show original charge and separate refund line with reference ID — not silent net. Card statements show gross charge; users panic if receipt shows only net after partial refund.

## Email timing and resend

Send within 60s of `payment_intent.succeeded` webhook. Queue retries on email provider failure. In-app "Resend receipt" on order detail — top support deflector.

## PDF accessibility

Tagged PDF structure for screen readers — not scanned images. Selectable invoice number text, 4.5:1 contrast, embedded fonts for print.

## Chargeback evidence bundle

Attach AVS, 3DS ECI, delivery proof, IP country to support-exportable bundle — representment teams need one click, not SQL.

## Dark mode email

Test Apple Mail dark mode — pure `#fff` backgrounds bloom. Use `color-scheme` meta and transparent PNG logos.

## Measuring conversion impact

Baseline checkout completion and step latency in RUM before UX changes. Ship payment UX behind flags; roll out on low-traffic weekday after issuer test card validation passes in staging.
## Order amendments post-receipt

Tip adjustments and post-delivery fees need amended receipt or supplemental invoice — never silent charge without new receipt email.

## Multi-currency receipts

Show paid currency prominently; secondary line in shopper browse currency if different. Exchange rate source and timestamp footnote for expense auditors.

## Print stylesheet

`@media print` hides nav and marketing — receipt fills page. Test print from Chrome mobile — users print to PDF for reimbursement.

## Accessibility in HTML email

Table layout for receipts still common — use `role="presentation"` and semantic headings for screen readers in email clients that strip style.

## Localization of date formats

`2026-07-17` vs `17/07/2026` — `Intl.DateTimeFormat` with user locale. US military and EU corporate expect different defaults.

## Receipt numbering gaps

Invoice sequences must be gapless in many jurisdictions — document void/credit note as separate sequence, not reuse number.

## In-app receipt scroll

Long item lists collapse with expand — LCP on order page is hero amount, not fiftieth line item.

## Warranty and legal footer

Link terms of sale on receipt email footer — dispute window and return policy visibility reduces chargebacks labeled "product not as described."

## Gift purchase receipts

Gift orders hide item prices on receipt — show "Gift" and delivery address only. Email to purchaser includes full detail separately.

## Tip line after delivery

Food delivery tip after receipt sent — send supplemental receipt or amended total push notification. Users dispute when tip added post-authorization without notice.

## Carbon or sustainability line

Optional receipt footer with carbon offset purchase — separate line item, not buried in fees.

## QR code on receipt

B2B receipts QR linking to VAT validation portal — EU e-invoicing trends require machine-readable invoice data.

## Archive and search in app

Users search order history by last4 or amount — receipt metadata indexed for search, not PDF-only storage.

## Pro forma vs paid invoice

Clear watermark "PAID" on settled invoice; pro forma before payment labeled "NOT A TAX INVOICE" — accounting teams require distinction.

## Attachment size limits

Email providers reject large PDF attachments — host receipt PDF on HTTPS link with auth cookie, email links only.

## Timezone on receipt

Show purchase timezone explicitly for travel merchants — "Purchased Jul 17, 2026 14:32 Europe/Berlin" avoids expense report confusion.
## Partial capture and auth hold receipts

Pre-auth hospitality flows should receipt the hold amount separately from final capture. Email subject "Authorization hold — not final charge" prevents guests from disputing pending line on credit statement.

## Marketplace seller splits

Two-sided marketplaces need seller line items and platform fee as distinct rows — buyers screenshot receipts for employer reimbursement; combined "marketplace charge" line gets expense reports rejected.

## Accessibility of PDF tables

Screen readers traverse invoice tables row by row — put total in `<tfoot>` with scope headers. WCAG technique for complex invoices audited separately from HTML checkout a11y.

## Cross-channel receipt consistency

The amount in email, PDF, in-app order detail, and push notification must match to the cent — users compare screenshots when finance rejects expenses. Build receipts from a single server-side template function; do not let the mobile client format currency independently. When tax or tip posts asynchronously, version the receipt (`receipt_version: 2`) and resend with clear "Updated total" subject lines rather than silent overwrite.

## B2B approval workflows

Enterprise buyers forward receipts to AP systems that parse invoice numbers with regex. Use stable, gapless numbering per legal entity; document credit notes as separate sequences. Include PO number field on checkout when `account_type=business` — missing PO is the top reason AP rejects otherwise valid receipts.

## Metrics that matter

Measure time-to-receipt-email (p95), resend rate, support contacts mentioning "receipt," and print/PDF download rate on mobile. Spikes in resend after deploy usually mean webhook retry duplication or wrong `to` address on guest checkout — alert when resend rate doubles week-over-week.

Receipt templates should include merchant descriptor exactly as it appears on card statements — mismatch drives "unrecognized charge" disputes independent of amount errors.

## Guest vs authenticated receipt flows

Guests need email capture before pay with double-entry validation — typos send receipts to wrong inboxes and generate chargebacks. Logged-in users should still confirm email on file at checkout when receipt legal name must match employer policy. For guest orders, deep link token in receipt email must expire in 7 days and require email match to open order detail — prevents receipt URL forwarding leaks.

## Archival and legal hold

Finance may require immutable receipt storage for seven years — object-lock S3 bucket or WORM storage separate from mutable app DB. Legal hold flag prevents delete-user GDPR erasure from removing receipt PDF until hold clears; document in privacy policy.

## Credits, vouchers, and negative lines

Store credit applied as tender appears as negative line with label "Account credit" — not mixed into tax lines. Users reconciling employer reimbursements need gross charge and credit as separate visible rows.

## Subscription renewal receipts

Recurring charge receipts should state billing period covered ("Apr 1–Apr 30") and cancellation policy link — reduces "what did I pay for?" contacts on SaaS renewals independent of payment method UX.

## White-label and marketplace receipts

Marketplace receipts must show both marketplace brand and seller legal name where regulation requires — buyers searching statement for seller name call support when only marketplace descriptor appears.

Include support phone and chat hours on PDF footer — receipts are often opened months later when live chat is closed.

Add `receipt_locale` to metadata so support reprints match language user checked out in — mixed EN receipt for DE checkout triggers expense rejection.

## Resources

- [Stripe — 3DS2 guide](https://stripe.com/docs/payments/3d-secure)
- [Adyen — Authentication documentation](https://docs.adyen.com/online-payments/3d-secure)
- [EMVCo 3-D Secure specification](https://www.emvco.com/emv-technologies/3d-secure/)
- [WCAG 2.2 — form accessibility](https://www.w3.org/WAI/WCAG22/quickref/)
- [web.dev — payment request API](https://web.dev/articles/payment-request-intro)
