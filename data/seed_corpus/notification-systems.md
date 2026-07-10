# Notification Systems

## Summary
A notification system delivers events to users across multiple channels (push, email, SMS, in-app) reliably at scale, balancing delivery guarantees, user preferences, and provider heterogeneity.

## Core Principles
- Fan-out architecture: a producer publishes to a queue/topic, and channel-specific workers consume and deliver independently, decoupling business events from delivery mechanics.
- Delivery is generally at-least-once; consumers and provider APIs must be idempotent, and clients dedupe on a notification ID to avoid duplicate pushes.
- User preference/consent state (opt-in/out per channel and category) must be checked before dispatch — legally required for email/SMS (CAN-SPAM, TCPA, GDPR).
- A channel abstraction layer normalizes provider differences (APNs, FCM, Twilio, SES) so the rest of the system doesn't branch on channel type.
- Templates are rendered per-user at send time, not baked into the event, so one event fans out correctly across languages/formats.
- Retry with exponential backoff and per-channel dead-lettering, since failure modes differ (expired device token vs SMTP soft bounce vs SMS carrier rejection).

## When to Use / When Not
- Use for any product needing timely, multi-channel communication decoupled from core transactional flows.
- Avoid a custom multi-provider abstraction at very low volume — direct SDK integration with one provider is simpler until scale justifies it.

## Tradeoffs
- At-least-once delivery with dedup vs exactly-once complexity — most systems accept rare duplicates over the cost of distributed transactional delivery.
- Real-time delivery vs batching for cost — high-volume SMS/push benefits from batching, adding latency.
- A centralized preference store simplifies compliance but adds a synchronous lookup on every send path.

## Common Patterns & Techniques
- A message queue (Kafka/SQS) between event source and channel workers absorbs bursts and lets channels scale independently.
- Device token lifecycle management: refresh/invalidate on provider feedback (APNs unregistered, FCM NotRegistered).
- Priority tiers: transactional messages (OTP, security alerts) bypass marketing queues via high-priority lanes.
- Digest/aggregation windows collapse many low-priority events (likes, mentions) into one periodic notification.

## Pitfalls
- Not deduping across retries, causing duplicate sends when a worker crashes mid-send and reprocesses the message.
- Ignoring provider-specific rate limits (FCM/APNs throttle per app), causing silent drops under load spikes.
- Coupling rendering to the triggering service instead of the fan-out worker, forcing redeploys for localization/template changes.

## Real-World Examples
- Meta's notification pipeline aggregates activity events and applies per-user relevance ranking before dispatch across push/email/in-app.
- Uber routes trip-status events to push, SMS, and in-app channels with priority-based delivery for time-critical alerts.
- Slack batches and dedups desktop/mobile push per channel/thread to avoid notification storms from active conversations.
</content>
<parameter name="i">Trim notification-systems note to fit word range