package com.mediscan.backend.dto;

import com.mediscan.backend.model.Scan;
import java.time.Instant;
import java.util.Map;

public final class ScanDtos {

    private ScanDtos() {
    }

    /** Row in the scan history list. */
    public record ScanSummary(
            Long id,
            String disease,
            String diseaseDisplay,
            String patientName,
            Integer patientAge,
            String prediction,
            Double confidence,
            Boolean conclusive,
            String modelStatus,
            String stage,
            String heatmapUrl,
            String reportUrl,
            Instant createdAt) {

        public static ScanSummary from(Scan scan) {
            return new ScanSummary(
                    scan.getId(),
                    scan.getDisease(),
                    scan.getDiseaseDisplay(),
                    scan.getPatientName(),
                    scan.getPatientAge(),
                    scan.getPrediction(),
                    scan.getConfidence(),
                    scan.getConclusive(),
                    scan.getModelStatus(),
                    scan.getStage(),
                    scan.getHeatmapUrl(),
                    scan.getReportUrl(),
                    scan.getCreatedAt());
        }
    }

    /**
     * Full analysis response: the raw ML payload plus the persisted scan id, so
     * the client can render every field the inference service reported without
     * the backend having to mirror its evolving schema.
     */
    public record AnalysisResponse(
            Long scanId,
            Map<String, Object> result) {
    }
}
