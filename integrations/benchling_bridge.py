"""
Glassbox + Benchling Integration
Validates AI-generated sequences before Benchling registration
"""
from benchling_sdk import Benchling
from glassbox_validator.pre_execution import PreExecutionValidator
import requests

class GlassboxBenchlingBridge:
    """
    Middleware layer between AI design systems and Benchling ELN
    """
    def __init__(self, benchling_api_key: str, benchling_tenant: str, glassbox_api_url: str):
        self.benchling = Benchling(
            url=f"https://{benchling_tenant}.benchling.com",
            auth_token=benchling_api_key
        )
        self.glassbox_url = glassbox_api_url
        self.validator = PreExecutionValidator()

    def register_validated_sequence(self, sequence: str, name: str, folder_id: str) -> str:
        """
        Validate sequence with Glassbox, then register in Benchling
        Returns:
        Benchling DNA sequence ID if successful
        """
        sbol_data = self._convert_to_sbol(sequence, name)
        validation_result = self._validate_with_glassbox(sbol_data)
        if not validation_result["is_valid"]:
            raise ValueError(f"Glassbox validation failed: {validation_result['errors']}")
        dna_sequence = self.benchling.dna_sequences.create(
            name=name,
            bases=sequence,
            folder_id=folder_id,
            custom_fields={
                "Glassbox Validation Status": "PASSED",
                "Glassbox Design Hash": validation_result["design_hash"],
                "Validation Timestamp": validation_result.get("timestamp")
            }
        )
        return dna_sequence.id

    def validate_benchling_sequence(self, sequence_id: str) -> dict:
        dna_seq = self.benchling.dna_sequences.get_by_id(sequence_id)
        sbol_data = self._convert_to_sbol(dna_seq.bases, dna_seq.name)
        return self._validate_with_glassbox(sbol_data)

    def _convert_to_sbol(self, sequence: str, name: str) -> bytes:
        import pySBOL3
        doc = pySBOL3.Document()
        component = pySBOL3.Component(f"design_{name}", pySBOL3.SBO_DNA)
        component.name = name
        seq = pySBOL3.Sequence(f"seq_{name}")
        seq.elements = sequence
        seq.encoding = pySBOL3.IUPAC_DNA_ENCODING
        component.sequences = [seq]
        doc.add(component)
        doc.add(seq)
        return doc.write_string().encode()

    def _validate_with_glassbox(self, sbol_data: bytes) -> dict:
        response = requests.post(
            f"{self.glassbox_url}/validate/design",
            files={"sbol_le": ("design.sbol", sbol_data)}
        )
        response.raise_for_status()
        return response.json()

if __name__ == "__main__":
    bridge = GlassboxBenchlingBridge(
        benchling_api_key="sk...",
        benchling_tenant="your-org",
        glassbox_api_url="https://glassbox-api.your-org.com"
    )
    ai_sequence = "ATGGCTAGCGGATCC..."
    try:
        seq_id = bridge.register_validated_sequence(
            sequence=ai_sequence,
            name="AI_GFP_variant_v23",
            folder_id="lib_abc123"
        )
        print(f"✓ Sequence registered: {seq_id}")
    except ValueError as e:
        print(f"✗ Validation failed: {e}")
