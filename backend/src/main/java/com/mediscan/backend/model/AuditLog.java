package com.mediscan.backend.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;

/** Minimal, payload-free audit event for protected API access. */
@Entity
@Table(name = "audit_logs")
public class AuditLog {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY) private Long id;
    @Column(nullable = false, length = 160) private String userId;
    @Column(length = 64) private String patientId;
    @Column(nullable = false, length = 16) private String method;
    @Column(nullable = false, length = 512) private String requestPath;
    @Column(nullable = false, length = 64) private String clientIp;
    @Column(nullable = false) private int responseStatus;
    @Column(nullable = false) private Instant occurredAt = Instant.now();

    protected AuditLog() { }

    public AuditLog(String userId, String patientId, String method, String requestPath, String clientIp, int responseStatus) {
        this.userId = userId;
        this.patientId = patientId;
        this.method = method;
        this.requestPath = requestPath;
        this.clientIp = clientIp;
        this.responseStatus = responseStatus;
    }
}
