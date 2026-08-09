package com.mediscan.backend.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.Lob;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import java.time.Instant;

/**
 * One screening run: the patient details submitted, plus everything the ML
 * service reported back. Model status and confidence are stored alongside the
 * prediction so a historical report can never be re-read as more certain than
 * it was at the time.
 */
@Entity
@Table(name = "scans")
public class Scan {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    @Column(nullable = false, length = 64)
    private String disease;

    @Column(length = 120)
    private String diseaseDisplay;

    @Column(nullable = false, length = 160)
    private String patientName;

    @Column(nullable = false)
    private Integer patientAge;

    @Column(length = 1000)
    private String patientNotes;

    @Column(length = 255)
    private String originalFilename;

    @Column(length = 200)
    private String prediction;

    @Column(length = 200)
    private String topClass;

    private Double confidence;

    private Boolean conclusive;

    @Column(length = 64)
    private String modelStatus;

    @Column(length = 200)
    private String stage;

    @Column(length = 512)
    private String heatmapUrl;

    @Column(length = 512)
    private String reportUrl;

    @Lob
    @Column(length = 8000)
    private String safetyWarning;

    @Column(nullable = false)
    private Instant createdAt = Instant.now();

    protected Scan() {
    }

    public Scan(User user, String disease, String patientName, Integer patientAge) {
        this.user = user;
        this.disease = disease;
        this.patientName = patientName;
        this.patientAge = patientAge;
    }

    public Long getId() {
        return id;
    }

    public User getUser() {
        return user;
    }

    public String getDisease() {
        return disease;
    }

    public String getDiseaseDisplay() {
        return diseaseDisplay;
    }

    public void setDiseaseDisplay(String diseaseDisplay) {
        this.diseaseDisplay = diseaseDisplay;
    }

    public String getPatientName() {
        return patientName;
    }

    public Integer getPatientAge() {
        return patientAge;
    }

    public String getPatientNotes() {
        return patientNotes;
    }

    public void setPatientNotes(String patientNotes) {
        this.patientNotes = patientNotes;
    }

    public String getOriginalFilename() {
        return originalFilename;
    }

    public void setOriginalFilename(String originalFilename) {
        this.originalFilename = originalFilename;
    }

    public String getPrediction() {
        return prediction;
    }

    public void setPrediction(String prediction) {
        this.prediction = prediction;
    }

    public String getTopClass() {
        return topClass;
    }

    public void setTopClass(String topClass) {
        this.topClass = topClass;
    }

    public Double getConfidence() {
        return confidence;
    }

    public void setConfidence(Double confidence) {
        this.confidence = confidence;
    }

    public Boolean getConclusive() {
        return conclusive;
    }

    public void setConclusive(Boolean conclusive) {
        this.conclusive = conclusive;
    }

    public String getModelStatus() {
        return modelStatus;
    }

    public void setModelStatus(String modelStatus) {
        this.modelStatus = modelStatus;
    }

    public String getStage() {
        return stage;
    }

    public void setStage(String stage) {
        this.stage = stage;
    }

    public String getHeatmapUrl() {
        return heatmapUrl;
    }

    public void setHeatmapUrl(String heatmapUrl) {
        this.heatmapUrl = heatmapUrl;
    }

    public String getReportUrl() {
        return reportUrl;
    }

    public void setReportUrl(String reportUrl) {
        this.reportUrl = reportUrl;
    }

    public String getSafetyWarning() {
        return safetyWarning;
    }

    public void setSafetyWarning(String safetyWarning) {
        this.safetyWarning = safetyWarning;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }
}
