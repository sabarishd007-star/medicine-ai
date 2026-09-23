"""FHIR DiagnosticReport serialization for AI screening results."""

from datetime import datetime, timezone
import json
from typing import Optional

try:
    from fhir.resources.codeableconcept import CodeableConcept
    from fhir.resources.coding import Coding
    from fhir.resources.diagnosticreport import DiagnosticReport
    from fhir.resources.reference import Reference
    FHIR_RESOURCES_AVAILABLE = True
except ImportError:
    FHIR_RESOURCES_AVAILABLE = False


def build_fhir_report(
    patient_id: str,
    diagnosis: str,
    confidence: float,
    doctor_notes: Optional[str] = None,
    modality: Optional[str] = "Pathology study"
) -> str:
    """Return a FHIR R4 DiagnosticReport JSON document."""
    if FHIR_RESOURCES_AVAILABLE:
        conclusion_str = f"MediScan AI Assessment: {diagnosis} (Confidence: {confidence:.2f}%)"
        if doctor_notes:
            conclusion_str += f". Notes: {doctor_notes}"

        report = DiagnosticReport(
            status="final",
            code=CodeableConcept(
                coding=[Coding(system="http://loinc.org", code="11526-1", display=modality or "Pathology study")]
            ),
            subject=Reference(reference=f"Patient/{patient_id}"),
            effectiveDateTime=datetime.now(timezone.utc).isoformat(),
            conclusion=conclusion_str,
        )
        return report.model_dump_json(indent=2)
    else:
        # Fallback compliant JSON schema if fhir.resources is not installed
        return json.dumps({
            "resourceType": "DiagnosticReport",
            "status": "final",
            "code": {
                "coding": [{
                    "system": "http://loinc.org",
                    "code": "11526-1",
                    "display": modality or "Pathology study"
                }]
            },
            "subject": {"reference": f"Patient/{patient_id}"},
            "effectiveDateTime": datetime.now(timezone.utc).isoformat(),
            "conclusion": f"MediScan AI Assessment: {diagnosis} (Confidence: {confidence:.2f}%)"
        }, indent=2)
