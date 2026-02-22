"""
Glassbox + Opentrons Integration
Validate designs before Opentrons protocol execution
"""
from opentrons import protocol_api
import requests
import json

class GlassboxOpentronsProtocol:
    """
    Base class for Opentrons protocols with Glassbox validation
    """
    def __init__(self, glassbox_api_url: str):
        self.glassbox_url = glassbox_api_url
        self.validation_results = []

    def validate_design(self, sbol_le_path: str) -> bool:
        with open(sbol_le_path, 'rb') as f:
            response = requests.post(
                f"{self.glassbox_url}/validate/design",
                files={"sbol_le": f}
            )
            result = response.json()
            self.validation_results.append(result)
            if not result["is_valid"]:
                print("❌ VALIDATION FAILED:")
                for error in result["errors"]:
                    print(f" {error}")
                return False
            print(f"✅ Design validated. Hash: {result['design_hash']}")
            return True

    def run_with_validation(self, protocol: protocol_api.ProtocolContext, design_les: list):
        for design_le in design_les:
            if not self.validate_design(design_le):
                raise ValueError(f"Design validation failed: {design_le}")
        print(" Starting Opentrons protocol...")
        return self.execute_protocol(protocol)

    def execute_protocol(self, protocol: protocol_api.ProtocolContext):
        raise NotImplementedError

metadata = {
    'protocolName': 'GFP Assembly with Glassbox Validation',
    'author': 'Your Lab',
    'apiLevel': '2.13'
}

def run(protocol: protocol_api.ProtocolContext):
    validator = GlassboxOpentronsProtocol(
        glassbox_api_url="https://glassbox-api.your-org.com"
    )
    designs_to_validate = [
        "/data/designs/promoter_j23100.sbol",
        "/data/designs/gfp_optimized.sbol",
        "/data/designs/terminator_b0015.sbol"
    ]
    for design in designs_to_validate:
        if not validator.validate_design(design):
            protocol.comment("❌ PROTOCOL ABORTED: Design validation failed")
            return
    protocol.comment("✅ All designs validated. Proceeding with assembly...")
    tips = protocol.load_labware('opentrons_96_tiprack_300ul', 1)
    plate = protocol.load_labware('nest_96_wellplate_200ul_at', 2)
    p300 = protocol.load_instrument('p300_single_gen2', 'right', tip_racks=[tips])
    p300.transfer(50, plate['A1'], plate['B1'])
    protocol.comment("✅ Protocol complete")
