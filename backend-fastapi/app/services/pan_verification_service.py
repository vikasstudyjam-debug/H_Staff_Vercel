import re
from typing import Dict, Any

class PANVerificationService:
    """
    Validates PAN structure and Individual ('P') entity designation.
    Distinguishes regex format validity from verified government identity.
    """
    PAN_REGEX = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$")

    @classmethod
    def verify_pan_card(cls, pan_number: str) -> Dict[str, Any]:
        clean_pan = pan_number.strip().upper()

        if not cls.PAN_REGEX.match(clean_pan):
            return {
                "format_valid": False,
                "is_individual": False,
                "status": "rejected",
                "reason": "Invalid PAN card format. Expected 5 letters, 4 digits, 1 letter."
            }

        # 4th character must be 'P' for Individual Gig Partners
        entity_char = clean_pan[3]
        if entity_char != 'P':
            return {
                "format_valid": True,
                "is_individual": False,
                "status": "rejected",
                "reason": f"Non-individual entity PAN '{entity_char}'. H-Staff gig partners must hold individual ('P') PAN."
            }

        return {
            "format_valid": True,
            "is_individual": True,
            "status": "format_verified_pending_nsdl",
            "pan_masked": f"{clean_pan[:2]}XXXXX{clean_pan[-2:]}",
            "note": "PAN format and individual entity check passed. Pending NSDL or admin confirmation."
        }

pan_service = PANVerificationService()