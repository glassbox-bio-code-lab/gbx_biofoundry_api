from glassbox_validator.post_execution import PostExecutionValidator

validator = PostExecutionValidator()
result = validator.validate_data("experiment_001_data.json", "experiment_001_provenance.sbol")
print(f"Quality Score: {result.quality_score:.2f}")
print(f"Provenance Valid: {result.provenance_chain_valid}")
if result.is_valid:
    print("✓ Data validated for AI retraining")
else:
    print("✗ Data validation failed:")
    for error in result.errors:
        print(f" - {error}")
