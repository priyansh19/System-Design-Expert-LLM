# ML Platforms & MLOps

## Summary
An ML platform is the infrastructure layer between "a data scientist trains a model in a notebook" and "that model reliably serves predictions in production" — it standardizes feature computation, experiment tracking, deployment, and monitoring so ML systems don't accumulate the specific kinds of technical debt unique to models (as opposed to regular software).

## Core Principles
- ML systems incur "hidden technical debt" beyond normal software debt: entanglement (changing one feature/model shifts everything downstream), feedback loops (a model's own predictions influence the data it's later trained on), and config/glue-code sprawl — this is the foundational argument for investing in platform abstractions rather than one-off pipelines.
- A feature store solves training/serving skew: the same feature computation logic (and, critically, the same point-in-time-correct data) must be used both when generating training data and when serving live predictions, or the model sees systematically different inputs in production than it did in training.
- Experiment tracking and model registries (MLflow) exist because "which exact code, data, and hyperparameters produced this deployed model" is a real operational question during an incident, not just a research nicety.
- Model monitoring must watch for data/concept drift, not just infrastructure health — a model can be "up" (serving low-latency responses) while silently degrading in accuracy because the input distribution has shifted since training.
- End-to-end platforms (TFX, Overton) that own ingestion through validation through serving reduce integration bugs at pipeline boundaries, at the cost of being a bigger, more opinionated system to adopt and operate.

## When to Use / When Not
- Invest in feature stores and formal experiment tracking once more than one team/model shares features or once "which model version is live and why" becomes a recurring incident-response question.
- A lightweight, ad-hoc pipeline (notebook -> script -> cron job) is perfectly reasonable for a single model with a single owner and low deployment frequency — platform investment should track actual pain, not anticipated scale.
- Automated retraining pipelines are valuable once data drifts fast enough that manual retraining cadence causes measurable accuracy loss; premature automation adds operational surface area for no benefit if the model is stable.

## Tradeoffs
- Platform standardization vs team velocity: a shared platform reduces duplicated infra work but can slow down teams whose use case doesn't fit its opinions well.
- Monitoring granularity vs cost/noise: fine-grained per-feature drift detection catches subtle degradation earlier but generates more alerts to triage and more compute/storage overhead.
- Retraining frequency vs stability/cost: retraining on every new batch of data keeps a model current but risks instability from noisy updates and costs real compute; too-infrequent retraining risks staleness.

## Common Patterns & Techniques
- Point-in-time correct joins in the feature store so training data never accidentally includes information from after the label's timestamp ("label leakage").
- Shadow deployment / canary rollout for models: serve the new model alongside the old one on a fraction of traffic (or log-only, no serving impact) before fully cutting over.
- Statistically rigorous CI for models (ease.ml/ci-style): treat accuracy regression like a build-breaking test failure, not a manual post-hoc check.
- Schema-based data validation (TFDV-style) catching upstream data pipeline bugs before they silently corrupt training data.

## Pitfalls
- Computing training features and serving features with two different code paths that quietly drift apart over time (the single most common cause of "works in offline eval, fails in production" bugs).
- Deploying model monitoring that only tracks system metrics (latency, error rate) and has no visibility into prediction distribution or downstream business metrics.
- Under-versioning: not tying a deployed model unambiguously to the exact training code, data snapshot, and hyperparameters that produced it.

## Real-World Examples
- Uber's Michelangelo and its underlying data platform standardized feature reuse and training/serving consistency across many internal ML teams.
- Google's TFX pipelines (ingestion -> validation -> training -> serving) shaped the industry's default mental model of what an ML platform looks like.
- Meta's Looper platform serves millions of ML-driven product decisions per second with built-in causal/Bayesian experimentation tooling for non-ML-expert engineers.
