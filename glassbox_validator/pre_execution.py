"""
Glassbox Bio Pre-Execution Validator
Validates AI-generated SBOL3 designs before robotic execution
"""
import pySBOL3
import re
from typing import Dict, List
from dataclasses import dataclass
import hashlib
from datetime import datetime

@dataclass
class ValidationResult:
    """Structured validation output"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    design_hash: str
    validation_timestamp: str

class PreExecutionValidator:
    """
    Validates AI-generated biological designs before wet-lab execution.
    Catches hallucinations, impossible sequences, and safety violations.
    """
    def __init__(self, cong: Dict = None):
        self.cong = cong or self._default_cong()
        self.biohazard_patterns = self._load_biohazard_db()

    def _default_cong(self) -> Dict:
        return {
            "max_sequence_length": 50000, # base pairs
            "min_sequence_length": 10,
            "allowed_nucleotides": set("ATGCatgc"),
            "forbidden_patterns": ["GAATTC" * 10], # homopolymers
            "enable_blast_check": False, # requires NCBI API
        }

    def _load_biohazard_db(self) -> List[str]:
        """Load pathogen/toxin sequence patterns (stub)"""
        return []  # In production: load from secure database

    def validate_design(self, sbol_uri: str) -> ValidationResult:
        """
        Main validation entrypoint.
        Args:
            sbol_uri: Path or URL to SBOL3 RDF document
        Returns:
            ValidationResult with pass/fail and detailed findings
        """
        errors = []
        warnings = []
        try:
            doc = pySBOL3.Document()
            doc.read(sbol_uri)
            components = doc.find_all(pySBOL3.Component)
            for component in components:
                errors.extend(self._check_sequence_validity(component))
                errors.extend(self._check_biohazard(component))
                warnings.extend(self._check_complexity(component))
                errors.extend(self._check_provenance(component))
            design_hash = self._compute_design_hash(doc)
            return ValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                design_hash=design_hash,
                validation_timestamp=self._get_timestamp()
            )
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                errors=[f"Parse error: {str(e)}"],
                warnings=[],
                design_hash="",
                validation_timestamp=self._get_timestamp()
            )

    def _check_sequence_validity(self, component: pySBOL3.Component) -> List[str]:
        """Validate DNA sequence integrity"""
        errors = []
        if not component.sequences:
            errors.append(f"Component {component.display_id} missing sequence")
            return errors
        for seq in component.sequences:
            seq_obj = seq.lookup()
            elements = seq_obj.elements
            if len(elements) > self.cong["max_sequence_length"]:
                errors.append(
                    f"Sequence {seq_obj.display_id} exceeds max length "
                    f"({len(elements)} > {self.cong['max_sequence_length']})"
                )
            if len(elements) < self.cong["min_sequence_length"]:
                errors.append(
                    f"Sequence {seq_obj.display_id} below min length "
                    f"({len(elements)} < {self.cong['min_sequence_length']})"
                )
            invalid_chars = set(elements) - self.cong["allowed_nucleotides"]
            if invalid_chars:
                errors.append(
                    f"Sequence {seq_obj.display_id} contains invalid characters: "
                    f"{invalid_chars}"
                )
            for forbidden in self.cong["forbidden_patterns"]:
                if forbidden in elements.upper():
                    errors.append(
                        f"Sequence {seq_obj.display_id} contains forbidden pattern: "
                        f"{forbidden[:20]}..."
                    )
        return errors

    def _check_biohazard(self, component: pySBOL3.Component) -> List[str]:
        """Screen for pathogen/toxin sequences"""
        errors = []
        if not component.sequences:
            return errors
        for seq in component.sequences:
            seq_obj = seq.lookup()
            elements = seq_obj.elements.upper()
            for hazard_pattern in self.biohazard_patterns:
                if hazard_pattern in elements:
                    errors.append(
                        f"BIOHAZARD ALERT: Sequence {seq_obj.display_id} "
                        f"matches restricted pathogen/toxin database"
                    )
        return errors

    def _check_complexity(self, component: pySBOL3.Component) -> List[str]:
        """Warn about overly complex designs (low synthesis success)"""
        warnings = []
        if not component.sequences:
            return warnings
        for seq in component.sequences:
            seq_obj = seq.lookup()
            elements = seq_obj.elements.upper()
            gc_content = (elements.count('G') + elements.count('C')) / len(elements)
            if gc_content < 0.3 or gc_content > 0.7:
                warnings.append(
                    f"Sequence {seq_obj.display_id} has suboptimal GC content: "
                    f"{gc_content:.1%} (recommend 40-60%)"
                )
            if self._has_high_repetition(elements):
                warnings.append(
                    f"Sequence {seq_obj.display_id} contains highly repetitive regions "
                    f"(may fail synthesis or PCR)"
                )
        return warnings

    def _has_high_repetition(self, sequence: str, window: int = 20) -> bool:
        """Detect repetitive sequences using sliding window"""
        seen = set()
        for i in range(len(sequence) - window):
            kmer = sequence[i:i+window]
            if kmer in seen:
                return True
            seen.add(kmer)
        return False

    def _check_provenance(self, component: pySBOL3.Component) -> List[str]:
        """Verify AI model provenance is documented"""
        errors = []
        if not hasattr(component, 'provenance') or not component.provenance():
            errors.append(
                f"Component {component.display_id} missing AI provenance "
                f"(prov:wasGeneratedBy required for audit trail)"
            )
        return errors

    def _compute_design_hash(self, doc: pySBOL3.Document) -> str:
        """Generate cryptographic hash for immutable audit trail"""
        content = doc.write_string()
        return hashlib.sha256(content.encode()).hexdigest()

    def _get_timestamp(self) -> str:
        return datetime.utcnow().isoformat() + "Z"
