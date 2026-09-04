"""FHIR DiagnosticReport serialization for AI screening results."""

from datetime import datetime, timezone

from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.coding import Coding
from fhir.resources.diagnosticreport import DiagnosticReport
from fhir.resources.reference import Reference


def build_fhir_report(patient_id: str, diagnosis: str, confidence: float) -> str:
    """Return a FHIR DiagnosticReport JSON document without patient PII."""
    report = DiagnosticReport(
        status="final",
        code=CodeableConcept(
            coding=[Coding(system="http://loinc.org", code="11526-1", display="Pathology study")]
        ),
        subject=Reference(reference=f"Patient/{patient_id}"),
        effectiveDateTime=datetime.now(timezone.utc).isoformat(),
        conclusion=f"MediScan AI Assessment: {diagnosis} (Confidence: {confidence:.2f}%)",
    )
    return report.model_dump_json()
