"""
Glassbox + TeselaGen Integration
Bidirectional validation between TeselaGen LIMS and Glassbox
"""
import requests
import json
from typing import Dict, List
import pySBOL3

class GlassboxTeselaGenBridge:
    """
    Integration layer for TeselaGen LIMS + Glassbox validation
    """
    def __init__(self, teselagen_url: str, teselagen_api_key: str, glassbox_api_url: str):
        self.teselagen_url = teselagen_url
        self.teselagen_headers = {
            "Authorization": f"Bearer {teselagen_api_key}",
            "Content-Type": "application/json"
        }
        self.glassbox_url = glassbox_api_url

    def validate_teselagen_design(self, design_id: str) -> Dict:
        design_data = self._fetch_teselagen_design(design_id)
        sbol_data = self._convert_teselagen_to_sbol(design_data)
        validation_result = self._validate_with_glassbox(sbol_data)
        self._update_teselagen_validation_status(design_id, validation_result)
        return validation_result

    def sync_experiment_results(self, experiment_id: str) -> Dict:
        exp_data = self._fetch_teselagen_experiment(experiment_id)
        allotrope_data = self._convert_to_allotrope(exp_data)
        provenance_sbol = self._fetch_experiment_provenance(experiment_id)
        validation = self._validate_experiment_data(allotrope_data, provenance_sbol)
        self._update_experiment_quality_score(experiment_id, validation["quality_score"])
        return validation

    def _fetch_teselagen_design(self, design_id: str) -> Dict:
        response = requests.get(
            f"{self.teselagen_url}/designs/{design_id}",
            headers=self.teselagen_headers
        )
        response.raise_for_status()
        return response.json()

    def _convert_teselagen_to_sbol(self, design_data: Dict) -> bytes:
        doc = pySBOL3.Document()
        component = pySBOL3.Component(design_data["id"], pySBOL3.SBO_DNA)
        component.name = design_data["name"]
        seq = pySBOL3.Sequence(f"seq_{design_data['id']}")
        seq.elements = design_data["sequence"]
        seq.encoding = pySBOL3.IUPAC_DNA_ENCODING
        component.sequences = [seq]
        doc.add(component)
        doc.add(seq)
        return doc.write_string().encode()

    def _validate_with_glassbox(self, sbol_data: bytes) -> Dict:
        response = requests.post(
            f"{self.glassbox_url}/validate/design",
            files={"sbol_le": ("design.sbol", sbol_data)}
        )
        response.raise_for_status()
        return response.json()

    def _update_teselagen_validation_status(self, design_id: str, validation: Dict):
        requests.patch(
            f"{self.teselagen_url}/designs/{design_id}",
            headers=self.teselagen_headers,
            json={
                "custom_fields": {
                    "glassbox_validation_status": "PASSED" if validation["is_valid"] else "FAILED",
                    "glassbox_design_hash": validation.get("design_hash"),
                    "glassbox_validation_errors": validation.get("errors", [])
                }
            }
        )

    def _fetch_teselagen_experiment(self, experiment_id: str) -> Dict:
        response = requests.get(
            f"{self.teselagen_url}/experiments/{experiment_id}/results",
            headers=self.teselagen_headers
        )
        response.raise_for_status()
        return response.json()

    def _convert_to_allotrope(self, exp_data: Dict) -> str:
        allotrope = {
            "$asm.manifest": "http://purl.allotrope.org/manifests/...",
            "measurement aggregate document": {
                "measurement document": exp_data["measurements"]
            }
        }
        return json.dumps(allotrope)

    def _fetch_experiment_provenance(self, experiment_id: str) -> str:
        response = requests.get(
            f"{self.teselagen_url}/experiments/{experiment_id}/provenance.sbol",
            headers=self.teselagen_headers
        )
        response.raise_for_status()
        return response.text

    def _validate_experiment_data(self, allotrope_json: str, provenance_sbol: str) -> Dict:
        files = {
            "allotrope_le": ("data.json", allotrope_json),
            "sbol_provenance_le": ("provenance.sbol", provenance_sbol)
        }
        response = requests.post(
            f"{self.glassbox_url}/validate/data",
            files=files
        )
        response.raise_for_status()
        return response.json()

    def _update_experiment_quality_score(self, experiment_id: str, quality_score: float):
        requests.patch(
            f"{self.teselagen_url}/experiments/{experiment_id}",
            headers=self.teselagen_headers,
            json={
                "quality_metrics": {
                    "glassbox_quality_score": quality_score
                }
            }
        )

if __name__ == "__main__":
    bridge = GlassboxTeselaGenBridge(
        teselagen_url="https://platform.teselagen.com/api",
        teselagen_api_key="your_api_key",
        glassbox_api_url="https://glassbox-api.your-org.com"
    )
    result = bridge.validate_teselagen_design("design_abc123")
    print(f"Design validation: {result['is_valid']}")
    exp_result = bridge.sync_experiment_results("exp_xyz789")
    print(f"Data quality score: {exp_result['quality_score']:.2%}")
