package com.mediscan.backend.service;

import com.mediscan.backend.dto.ScanDtos.AnalysisResponse;
import com.mediscan.backend.dto.ScanDtos.ScanSummary;
import com.mediscan.backend.model.Scan;
import com.mediscan.backend.model.User;
import com.mediscan.backend.repository.ScanRepository;
import java.util.List;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;

@Service
public class ScanService {

    private final ScanRepository scans;
    private final MlClient ml;

    public ScanService(ScanRepository scans, MlClient ml) {
        this.scans = scans;
        this.ml = ml;
    }

    public AnalysisResponse analyze(
            User user,
            String disease,
            String patientName,
            Integer patientAge,
            String patientNotes,
            MultipartFile file) {

        if (file == null || file.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "A scan image is required.");
        }

        Map<String, Object> result =
                ml.predict(disease, patientName, patientAge, patientNotes, file);
        if (result == null) {
            throw new MlClient.MlServiceException("Inference returned an empty response.");
        }

        Scan scan = new Scan(user, disease, patientName, patientAge);
        scan.setPatientNotes(patientNotes);
        scan.setOriginalFilename(file.getOriginalFilename());
        scan.setDiseaseDisplay(str(result.get("disease_display")));
        scan.setPrediction(str(result.get("prediction")));
        scan.setTopClass(str(result.get("top_class")));
        scan.setConfidence(dbl(result.get("confidence")));
        scan.setConclusive(bool(result.get("is_conclusive")));
        scan.setModelStatus(str(result.get("model_status")));
        scan.setStage(str(result.get("stage")));
        scan.setHeatmapUrl(str(result.get("heatmap_url")));
        scan.setReportUrl(str(result.get("report_url")));
        scan.setSafetyWarning(str(result.get("safety_warning")));
        scans.save(scan);

        return new AnalysisResponse(scan.getId(), result);
    }

    public List<ScanSummary> history(User user) {
        return scans.findByUserOrderByCreatedAtDesc(user).stream().map(ScanSummary::from).toList();
    }

    public ScanSummary get(User user, Long id) {
        return scans.findByIdAndUser(id, user)
                .map(ScanSummary::from)
                .orElseThrow(() ->
                        new ResponseStatusException(HttpStatus.NOT_FOUND, "Scan not found."));
    }

    public void delete(User user, Long id) {
        Scan scan = scans.findByIdAndUser(id, user).orElseThrow(() ->
                new ResponseStatusException(HttpStatus.NOT_FOUND, "Scan not found."));
        scans.delete(scan);
    }

    /**
     * Streams a report or heatmap belonging to the caller. The path is taken from
     * the stored record rather than from the request, so one user cannot read
     * another user's artifacts by guessing a filename.
     */
    public byte[] artifact(User user, Long scanId, String kind) {
        Scan scan = scans.findByIdAndUser(scanId, user).orElseThrow(() ->
                new ResponseStatusException(HttpStatus.NOT_FOUND, "Scan not found."));

        String path = "report".equals(kind) ? scan.getReportUrl() : scan.getHeatmapUrl();
        if (path == null || path.isBlank()) {
            throw new ResponseStatusException(
                    HttpStatus.NOT_FOUND, "No " + kind + " available for this scan.");
        }
        return ml.fetchBinary(path);
    }

    private static String str(Object value) {
        return value == null ? null : String.valueOf(value);
    }

    private static Double dbl(Object value) {
        return value instanceof Number number ? number.doubleValue() : null;
    }

    private static Boolean bool(Object value) {
        return value instanceof Boolean flag ? flag : null;
    }
}
