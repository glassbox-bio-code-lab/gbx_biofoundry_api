"""
Glassbox + Emerald Cloud Lab Integration
Validation decorator for ECL experiments
"""
from ecl import Experiment
from glassbox_validator.pre_execution import PreExecutionValidator
from glassbox_validator.post_execution import PostExecutionValidator
import functools
import json

def validate_ecl_experiment(glassbox_api_url: str):
    """
    Decorator to add Glassbox validation to ECL experiments
    Usage:
    @validate_ecl_experiment("https://glassbox-api.your-org.com")
    def my_experiment():
        # ECL experiment code
        pass
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            print(" Pre-execution validation...")
            exp = Experiment()
            design_metadata = exp.get_metadata()
            if "sbol_uri" in design_metadata:
                validator = PreExecutionValidator()
                result = validator.validate_design(design_metadata["sbol_uri"])
                if not result.is_valid:
                    raise ValueError(
                        "Glassbox pre-execution validation failed:\n" +
                        "\n".join(f" - {e}" for e in result.errors)
                    )
                print(f"✓ Design validated. Hash: {result.design_hash}")
            print(" Executing experiment...")
            result = func(*args, **kwargs)
            print(" Post-execution validation...")
            post_validator = PostExecutionValidator()
            data_validation = post_validator.validate_data(
                result.get("data_le"),
                result.get("provenance_le")
            )
            if not data_validation.is_valid:
                print("⚠ Data quality issues detected:")
                for warning in data_validation.warnings:
                    print(f" - {warning}")
            print(f" Data quality score: {data_validation.quality_score:.2%}")
            return result
        return wrapper
    return decorator

@validate_ecl_experiment("https://glassbox-api.your-org.com")
def gfp_expression_assay():
    """ECL experiment with automatic Glassbox validation"""
    from ecl import Experiment, Container, MeasurePlateAbsorbance
    exp = Experiment()
    exp.set_metadata({"sbol_uri": "https://designs.your-org.com/gfp_v23.sbol"})
    plate = Container("96-well plate")
    # ... ECL experiment instructions ...
    data = MeasurePlateAbsorbance(
        plate,
        wavelength=600,
        label="od600_growth"
    )
    return {
        "data_le": data.to_allotrope_json(),
        "provenance_le": exp.export_provenance_sbol()
    }

if __name__ == "__main__":
    result = gfp_expression_assay()
    print(f"Experiment complete. Data quality: {result['quality_score']}")
