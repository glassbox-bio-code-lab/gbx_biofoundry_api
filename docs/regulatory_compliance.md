# Regulatory Compliance Mapping

## NIST AI Risk Management Framework Alignment

| NIST RMF Function | Glassbox Implementation                                                 |
| ----------------- | ----------------------------------------------------------------------- |
| Govern            | Provenance tracking via prov:wasGeneratedBy ensures accountability      |
| Map               | Pre-execution validation maps AI capabilities to biological feasibility |
| Measure           | Quality scores (0.0-1.0) quantify data fitness for AI training          |
| Manage            | Post-execution validation manages AI drift via outlier detection        |

## FDA/CDER Draft Guidance Readiness

1. Continuous validation: Glassbox provides per-experiment validation
2. Data integrity: Cryptographic hashes ensure immutable audit trails
3. Explainability: Validation reports specify exactly which checks failed
4. Human oversight: Quality score thresholds trigger human review
