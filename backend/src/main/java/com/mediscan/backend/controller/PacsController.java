package com.mediscan.backend.controller;

import com.mediscan.backend.service.MlClient;
import java.util.Map;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/** Doctor/radiologist gateway for DICOMweb. AuditLogFilter records every request. */
@RestController
@RequestMapping("/api/doctor/pacs")
public class PacsController {
    private final MlClient ml;
    public PacsController(MlClient ml) { this.ml = ml; }

    @GetMapping("/studies")
    public ResponseEntity<Map<String, Object>> studies(@RequestParam String patientId, @RequestParam String justification,
            @RequestParam(defaultValue = "25") int limit) {
        requireJustification(justification);
        return ResponseEntity.ok(ml.pacsSearch(patientId, limit));
    }

    @GetMapping("/analyze-instance")
    public ResponseEntity<Map<String, Object>> analyze(@RequestParam String patientId, @RequestParam String studyUid, @RequestParam String seriesUid,
            @RequestParam String sopUid, @RequestParam String disease, @RequestParam String justification) {
        requireJustification(justification);
        return ResponseEntity.ok(ml.pacsAnalyze(studyUid, seriesUid, sopUid, disease));
    }

    private void requireJustification(String value) {
        if (value == null || value.isBlank()) throw new IllegalArgumentException("Access justification is required.");
    }
}
