from glassbox_validator.pre_execution import PreExecutionValidator

validator = PreExecutionValidator()
result = validator.validate_design("design_123.sbol")
if result.is_valid:
    print(f"✓ Design validated. Hash: {result.design_hash}")
else:
    print(f"✗ Validation failed:")
    for error in result.errors:
        print(f" - {error}")
