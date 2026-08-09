package com.mediscan.backend.controller;

import com.mediscan.backend.dto.ScanDtos.AnalysisResponse;
import com.mediscan.backend.dto.ScanDtos.ScanSummary;
import com.mediscan.backend.service.AuthService;
import com.mediscan.backend.service.MlClient;
import com.mediscan.backend.service.ScanService;
import java.security.Principal;
import java.util.List;
import java.util.Map;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/api")
@CrossOrigin
public class ScanController {

    private final ScanService scanService;
    private final AuthService auth;
    private final MlClient ml;

    public ScanController(ScanService scanService, AuthService auth, MlClient ml) {
        this.scanService = scanService;
        this.auth = auth;
        this.ml = ml;
    }

    /** Public: the disease catalogue, including model status and measured metrics. */
    @GetMapping("/diseases")
    public ResponseEntity<Map<String, Object>> diseases() {
        return ResponseEntity.ok(ml.listDiseases());
    }

    @GetMapping("/health")
    public ResponseEntity<Map<String, Object>> health() {
        return ResponseEntity.ok(Map.of("backend", "ok", "ml", ml.health()));
    }

    @PostMapping(value = "/scans/analyze", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<AnalysisResponse> analyze(
            Principal principal,
            @RequestParam("disease") String disease,
            @RequestParam("patientName") String patientName,
            @RequestParam("patientAge") Integer patientAge,
            @RequestParam(value = "patientNotes", required = false) String patientNotes,
            @RequestParam("file") MultipartFile file) {

        var user = auth.requireUser(principal == null ? null : principal.getName());
        return ResponseEntity.ok(
                scanService.analyze(user, disease, patientName, patientAge, patientNotes, file));
    }

    @GetMapping("/scans")
    public ResponseEntity<List<ScanSummary>> history(Principal principal) {
        var user = auth.requireUser(principal == null ? null : principal.getName());
        return ResponseEntity.ok(scanService.history(user));
    }

    @GetMapping("/scans/{id}")
    public ResponseEntity<ScanSummary> one(Principal principal, @PathVariable Long id) {
        var user = auth.requireUser(principal == null ? null : principal.getName());
        return ResponseEntity.ok(scanService.get(user, id));
    }

    @DeleteMapping("/scans/{id}")
    public ResponseEntity<Void> delete(Principal principal, @PathVariable Long id) {
        var user = auth.requireUser(principal == null ? null : principal.getName());
        scanService.delete(user, id);
        return ResponseEntity.noContent().build();
    }

    @GetMapping("/scans/{id}/report")
    public ResponseEntity<byte[]> report(Principal principal, @PathVariable Long id) {
        var user = auth.requireUser(principal == null ? null : principal.getName());
        byte[] pdf = scanService.artifact(user, id, "report");
        return ResponseEntity.ok()
                .contentType(MediaType.APPLICATION_PDF)
                .header(HttpHeaders.CONTENT_DISPOSITION,
                        "attachment; filename=\"MediScan_Report_" + id + ".pdf\"")
                .body(pdf);
    }

    @GetMapping("/scans/{id}/heatmap")
    public ResponseEntity<byte[]> heatmap(Principal principal, @PathVariable Long id) {
        var user = auth.requireUser(principal == null ? null : principal.getName());
        byte[] image = scanService.artifact(user, id, "heatmap");
        return ResponseEntity.ok().contentType(MediaType.IMAGE_PNG).body(image);
    }
}
