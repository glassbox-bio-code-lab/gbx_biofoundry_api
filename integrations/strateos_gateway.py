"""
Glassbox + Strateos/Transcriptic Integration
Validates Autoprotocol before submission to cloud lab
"""
import json
import requests
from typing import Dict, List

class GlassboxStrateosGateway:
    """
    Pre-execution validation gateway for Strateos protocols
    """
    def __init__(self, glassbox_api_url: str, strateos_api_key: str):
        self.glassbox_url = glassbox_api_url
        self.strateos_headers = {
            "X-User-Email": "your-email@example.com",
            "X-User-Token": strateos_api_key,
            "Content-Type": "application/json"
        }

    def submit_validated_protocol(self, autoprotocol: Dict, project_id: str) -> str:
        validation_errors = self._validate_autoprotocol_structure(autoprotocol)
        if validation_errors:
            raise ValueError(f"Protocol errors: {validation_errors}")
        sbol_refs = self._extract_sbol_references(autoprotocol)
        for sbol_uri in sbol_refs:
            result = self._validate_design(sbol_uri)
            if not result["is_valid"]:
                raise ValueError(f"Design {sbol_uri} validation failed: {result['errors']}")
        run_id = self._submit_to_strateos(autoprotocol, project_id)
        print(f"✓ Protocol validated and submitted. Run ID: {run_id}")
        return run_id

    def _validate_autoprotocol_structure(self, protocol: Dict) -> List[str]:
        errors = []
        if "instructions" not in protocol:
            errors.append("Missing 'instructions' field")
        required_ops = {"transfer", "incubate", "absorbance", "fluorescence"}
        present_ops = {instr.get("op") for instr in protocol.get("instructions", [])}
        if not present_ops:
            errors.append("No valid operations found")
        return errors

    def _extract_sbol_references(self, protocol: Dict) -> List[str]:
        sbol_refs = []
        metadata = protocol.get("metadata", {})
        if "design_uri" in metadata:
            sbol_refs.append(metadata["design_uri"])
        for instruction in protocol.get("instructions", []):
            if "design_uri" in instruction:
                sbol_refs.append(instruction["design_uri"])
        return sbol_refs

    def _validate_design(self, sbol_uri: str) -> Dict:
        sbol_response = requests.get(sbol_uri)
        sbol_data = sbol_response.content
        response = requests.post(
            f"{self.glassbox_url}/validate/design",
            files={"sbol_le": ("design.sbol", sbol_data)}
        )
        response.raise_for_status()
        return response.json()

    def _submit_to_strateos(self, protocol: Dict, project_id: str) -> str:
        response = requests.post(
            "https://secure.transcriptic.com/api/runs",
            headers=self.strateos_headers,
            json={
                "project_id": project_id,
                "protocol": protocol
            }
        )
        response.raise_for_status()
        return response.json()["id"]

if __name__ == "__main__":
    gateway = GlassboxStrateosGateway(
        glassbox_api_url="https://glassbox-api.your-org.com",
        strateos_api_key="your_api_key"
    )
    with open("ai_generated_protocol.json") as f:
        protocol = json.load(f)
    try:
        run_id = gateway.submit_validated_protocol(protocol, project_id="p1abc123")
        print(f"✓ Run submitted: {run_id}")
    except ValueError as e:
        print(f"✗ Submission blocked: {e}")
