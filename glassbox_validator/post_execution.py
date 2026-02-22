"""
Glassbox Bio Post-Execution Validator
Validates wet-lab data before feeding back to AI models
"""
import json
import jsonschema
from typing import Dict, List, Tuple
from dataclasses import dataclass
import pandas as pd
import numpy as np
from datetime import datetime
import pySBOL3
import hashlib

@dataclass
class DataValidationResult:
    """Structured data validation output"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    quality_score: float  # 0.0-1.0
    provenance_chain_valid: bool
    metadata_hash: str

class PostExecutionValidator:
    """
    Validates experimental data from autonomous wet labs before AI retraining.
    Detects metadata corruption, hardware anomalies, and broken provenance chains.
    """
    def __init__(self, cong: Dict = None):
        self.cong = cong or self._default_cong()
        self.allotrope_schema = self._load_allotrope_schema()

    def _default_cong(self) -> Dict:
        return {
            "min_sample_count": 3,
            "max_cv_percent": 25.0, # coefficient of variation
            "outlier_threshold_sigma": 3.0,
            "require_device_metadata": True,
            "require_timestamp": True,
        }

    def _load_allotrope_schema(self) -> Dict:
        """Load Allotrope ASM JSON schema for validation"""
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "required": ["$asm.manifest", "measurement aggregate document"],
            "properties": {
                "$asm.manifest": {"type": "string"},
                "measurement aggregate document": {"type": "object"}
            }
        }

    def validate_data(self, allotrope_le: str, sbol_provenance_le: str) -> DataValidationResult:
        """
        Main validation entrypoint for wet-lab data.
        Args:
            allotrope_le: Path to Allotrope ADF/ASM JSON
            sbol_provenance_le: Path to SBOL3 RDF with experiment metadata
        Returns:
            DataValidationResult with quality score and findings
        """
        errors = []
        warnings = []
        try:
            with open(allotrope_le) as f:
                allotrope_data = json.load(f)
            errors.extend(self._validate_allotrope_schema(allotrope_data))
            errors.extend(self._check_metadata_completeness(allotrope_data))
            warnings.extend(self._detect_outliers(allotrope_data))
            warnings.extend(self._check_instrument_qc(allotrope_data))
            sbol_doc = pySBOL3.Document()
            sbol_doc.read(sbol_provenance_le)
            provenance_valid, prov_errors = self._validate_provenance_chain(sbol_doc, allotrope_data)
            errors.extend(prov_errors)
            quality_score = self._compute_quality_score(allotrope_data, len(errors), len(warnings))
            metadata_hash = self._compute_metadata_hash(allotrope_data)
            return DataValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                quality_score=quality_score,
                provenance_chain_valid=provenance_valid,
                metadata_hash=metadata_hash
            )
        except Exception as e:
            return DataValidationResult(
                is_valid=False,
                errors=[f"Parse error: {str(e)}"],
                warnings=[],
                quality_score=0.0,
                provenance_chain_valid=False,
                metadata_hash=""
            )

    def _validate_allotrope_schema(self, data: Dict) -> List[str]:
        errors = []
        try:
            jsonschema.validate(instance=data, schema=self.allotrope_schema)
        except jsonschema.exceptions.ValidationError as e:
            errors.append(f"Allotrope schema violation: {e.message}")
        return errors

    def _check_metadata_completeness(self, data: Dict) -> List[str]:
        errors = []
        measurement_doc = data.get("measurement aggregate document", {}).get("measurement document", [])
        if not measurement_doc:
            errors.append("No measurement documents found in Allotrope data")
            return errors
        for i, doc in enumerate(measurement_doc):
            if self.cong["require_timestamp"] and not doc.get("measurement time"):
                errors.append(f"Measurement {i}: Missing timestamp")
            if self.cong["require_device_metadata"]:
                device = doc.get("device system document", {})
                if not device.get("device identier"):
                    errors.append(f"Measurement {i}: Missing device identier")
                if not device.get("rmware version"):
                    errors.append(f"Measurement {i}: Missing rmware version")
        return errors

    def _detect_outliers(self, data: Dict) -> List[str]:
        warnings = []
        measurement_docs = data.get("measurement aggregate document", {}).get("measurement document", [])
        for doc in measurement_docs:
            uor_agg = doc.get("uorescence point detection aggregate document", {})
            uor_docs = uor_agg.get("uorescence point detection document", [])
            if not uor_docs:
                continue
            values = [fd.get("uorescence", {}).get("value") for fd in uor_docs if fd.get("uorescence", {}).get("value") is not None]
            if len(values) < self.cong["min_sample_count"]:
                warnings.append(
                    f"Measurement {doc.get('measurement identier')}: Insufficient replicates ({len(values)} < {self.cong['min_sample_count']})"
                )
                continue
            values_array = np.array(values)
            mean = np.mean(values_array)
            std = np.std(values_array)
            if std > 0:
                z_scores = np.abs((values_array - mean) / std)
                outlier_indices = np.where(z_scores > self.cong["outlier_threshold_sigma"])[0]
                if len(outlier_indices) > 0:
                    warnings.append(
                        f"Measurement {doc.get('measurement identier')}: Detected {len(outlier_indices)} outliers (>{self.cong['outlier_threshold_sigma']}σ)"
                    )
            if mean > 0:
                cv = (std / mean) * 100
                if cv > self.cong["max_cv_percent"]:
                    warnings.append(
                        f"Measurement {doc.get('measurement identier')}: High variability (CV={cv:.1f}% > {self.cong['max_cv_percent']}%)"
                    )
        return warnings

    def _check_instrument_qc(self, data: Dict) -> List[str]:
        warnings = []
        measurement_docs = data.get("measurement aggregate document", {}).get("measurement document", [])
        for doc in measurement_docs:
            qc_status = doc.get("quality control aggregate document", {})
            if qc_status.get("instrument_warning"):
                warnings.append(
                    f"Measurement {doc.get('measurement identier')}: Instrument QC warning detected"
                )
        return warnings

    def _validate_provenance_chain(self, sbol_doc: pySBOL3.Document, allotrope_data: Dict) -> Tuple[bool, List[str]]:
        errors = []
        exp_data = sbol_doc.find_all(pySBOL3.ExperimentalData)
        if not exp_data:
            errors.append("SBOL document missing ExperimentalData objects")
            return False, errors
        for data_obj in exp_data:
            if not hasattr(data_obj, 'generated_by') or not data_obj.generated_by:
                errors.append(
                    f"ExperimentalData {data_obj.display_id} missing prov:wasGeneratedBy link to Experiment"
                )
                continue
            experiment = data_obj.generated_by[0].lookup()
            if not hasattr(experiment, 'members') or not experiment.members:
                errors.append(
                    f"Experiment {experiment.display_id} missing sbol:member link to Implementation"
                )
                continue
            implementation = experiment.members[0].lookup()
            if not hasattr(implementation, 'built') or not implementation.built:
                errors.append(
                    f"Implementation {implementation.display_id} missing sbol:built link to original Component design"
                )
        provenance_valid = len(errors) == 0
        return provenance_valid, errors

    def _compute_quality_score(self, data: Dict, error_count: int, warning_count: int) -> float:
        score = 1.0
        score -= error_count * 0.3
        score -= warning_count * 0.05
        measurement_docs = data.get("measurement aggregate document", {}).get("measurement document", [])
        for doc in measurement_docs:
            uor_agg = doc.get("uorescence point detection aggregate document", {})
            uor_docs = uor_agg.get("uorescence point detection document", [])
            values = [fd.get("uorescence", {}).get("value") for fd in uor_docs if fd.get("uorescence", {}).get("value") is not None]
            if len(values) >= 3:
                mean = np.mean(values)
                std = np.std(values)
                cv = (std / mean) * 100 if mean > 0 else 0
                if cv > 15:
                    score -= 0.1
        return max(0.0, min(1.0, score))

    def _compute_metadata_hash(self, data: Dict) -> str:
        metadata_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(metadata_str.encode()).hexdigest()
