# Payment Processing Systems

## Summary
Payment systems move money between parties exactly once despite network failures and retries, requiring idempotency, an auditable ledger, and careful handling of multi-step transactions spanning external, non-transactional providers.

## Core Principles
- Idempotency keys: every payment request carries a client-generated key so retried requests apply the charge exactly once instead of double-charging.
- Double-entry ledger: every transaction records at least two balanced entries (debit one account, credit another); the ledger is append-only and self-verifying.
- State machines model payment lifecycle explicitly (created → authorized → captured → settled → refunded), and only valid transitions are allowed.
- The Saga pattern coordinates a multi-step transaction (reserve inventory, charge card, ship) across services without distributed transactions, using compensating actions on failure.
- PCI-DSS mandates raw card data never touch your servers — tokenization means your systems store only opaque references.

## When to Use / When Not
- Use full ledger + saga architecture for any system handling real money movement, marketplaces, or multi-party splits (platform fees, payouts).
- A thin passthrough to a processor's hosted checkout is sufficient for simple single-item purchases with no internal balance tracking.
- Avoid custom card-data handling to reduce PCI scope — use tokenized processor SDKs unless you have dedicated compliance infrastructure.

## Tradeoffs
- Strong idempotency/ledger guarantees add write latency and storage overhead, but double charges or unbalanced books are unacceptable.
- Synchronous confirmation gives immediate certainty vs async webhooks scale better but require handling out-of-order/duplicate delivery.
- Sagas avoid distributed transactions across services but require carefully designed, idempotent compensating actions for every step.

## Common Patterns & Techniques
- Two-phase charge: authorize (hold funds) then capture (settle) separately, allowing cancellation before funds actually move.
- Outbox pattern to atomically record "charge processor" as a durable, retryable job alongside the local DB write.
- Webhook signature verification and replay-safe handlers for processor callbacks.
- Exactly-once *effect*, not exactly-once delivery: accept at-least-once retries but make the handler idempotent via a unique constraint on transaction ID.

## Pitfalls
- Treating a webhook as guaranteed single-delivery and not deduping, leading to double fulfillment on provider retries.
- Storing account balances as a single mutable integer instead of deriving them from the ledger, losing the audit trail.
- Skipping reconciliation, letting silent drift between internal state and the processor's ground truth go undetected for weeks.

## Real-World Examples
- Stripe's API requires an `Idempotency-Key` header on all mutating requests and uses a double-entry-style ledger for balances.
- Square's platform uses saga-style compensating transactions across order, inventory, and payment services.
- Marketplaces like Airbnb use split-ledger accounting to track host payouts, platform fees, and guest charges as balanced entries.
</content>
<parameter name="i">Rewrite payment-processing tighter