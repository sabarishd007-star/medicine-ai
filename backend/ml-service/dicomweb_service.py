"""Internal DICOMweb PACS client implementing QIDO-RS, WADO-RS, and STOW-RS."""
import os
from io import BytesIO
from typing import Any, Optional

try:
    import requests
    from pydicom import dcmread
    from pydicom.dataset import Dataset
    from requests_toolbelt.multipart import decoder
    from requests_toolbelt.multipart.encoder import MultipartEncoder
    PYDICOM_AVAILABLE = True
except ImportError:
    PYDICOM_AVAILABLE = False
    Dataset = Any
    dcmread = None

class DICOMwebError(RuntimeError):
    pass


class DICOMwebPACSClient:
    def __init__(self, base_url: Optional[str] = None, timeout: int = 30) -> None:
        self.base_url = (base_url or os.getenv("PACS_DICOMWEB_URL", "http://localhost:8042/dicom-web")).rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.verify = os.getenv("PACS_VERIFY_TLS", "true").lower() not in {"0", "false", "no"}
        token = os.getenv("PACS_OAUTH_TOKEN")
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        elif os.getenv("PACS_BASIC_USERNAME") and os.getenv("PACS_BASIC_PASSWORD"):
            self.session.auth = (os.environ["PACS_BASIC_USERNAME"], os.environ["PACS_BASIC_PASSWORD"])

    def search_studies(self, patient_id: str, limit: int = 25) -> list[dict[str, Any]]:
        response = self._request("GET", f"{self.base_url}/studies", params={"PatientID": patient_id, "limit": max(1, min(limit, 100))}, headers={"Accept": "application/dicom+json"})
        try:
            payload = response.json()
        except ValueError as exc:
            raise DICOMwebError("PACS returned invalid QIDO-RS JSON.") from exc
        if not isinstance(payload, list):
            raise DICOMwebError("PACS returned an unexpected QIDO-RS response.")
        return payload

    def retrieve_instance(self, study_uid: str, series_uid: str, sop_uid: str) -> Dataset:
        response = self._request("GET", f"{self.base_url}/studies/{study_uid}/series/{series_uid}/instances/{sop_uid}", headers={"Accept": 'multipart/related; type="application/dicom"'})
        try:
            content = next(part.content for part in decoder.MultipartDecoder.from_response(response).parts if part.content) if response.headers.get("Content-Type", "").lower().startswith("multipart/") else response.content
            return dcmread(BytesIO(content), force=False)
        except Exception as exc:
            raise DICOMwebError("PACS response was not a valid DICOM instance.") from exc

    def store_instances(self, datasets: list[Dataset]) -> bool:
        if not datasets:
            raise ValueError("At least one DICOM dataset is required.")
        fields = []
        for index, dataset in enumerate(datasets):
            output = BytesIO()
            dataset.save_as(output, enforce_file_format=True)
            fields.append((f"instance_{index}", (f"instance_{index}.dcm", output.getvalue(), "application/dicom")))
        body = MultipartEncoder(fields=fields)
        return self._request("POST", f"{self.base_url}/studies", data=body, headers={"Content-Type": f'multipart/related; type="application/dicom"; boundary={body.boundary_value}'}, accepted={200, 202}).status_code in {200, 202}

    def _request(self, method: str, url: str, accepted: set[int] = {200}, **kwargs: Any) -> requests.Response:
        try:
            response = self.session.request(method, url, timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            raise DICOMwebError("Could not communicate with the configured PACS.") from exc
        if response.status_code not in accepted:
            raise DICOMwebError(f"PACS request failed with HTTP {response.status_code}.")
        return response
