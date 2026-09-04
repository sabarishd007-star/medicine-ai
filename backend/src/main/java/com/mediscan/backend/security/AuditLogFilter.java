package com.mediscan.backend.security;

import com.mediscan.backend.model.AuditLog;
import com.mediscan.backend.repository.AuditLogRepository;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/** Records metadata for authenticated API activity without persisting request bodies or tokens. */
@Component
public class AuditLogFilter extends OncePerRequestFilter {
    private static final Logger log = LoggerFactory.getLogger(AuditLogFilter.class);
    private final AuditLogRepository auditLogs;

    public AuditLogFilter(AuditLogRepository auditLogs) { this.auditLogs = auditLogs; }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        try {
            chain.doFilter(request, response);
        } finally {
            Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
            if (authentication != null && authentication.isAuthenticated() && request.getRequestURI().startsWith("/api/")) {
                try {
                    auditLogs.save(new AuditLog(authentication.getName(), patientId(request), request.getMethod(),
                            request.getRequestURI(), clientIp(request), response.getStatus()));
                } catch (RuntimeException ex) {
                    log.error("Could not persist audit event", ex);
                }
            }
        }
    }

    private String patientId(HttpServletRequest request) {
        String[] path = request.getRequestURI().split("/");
        return path.length > 3 && "scans".equals(path[2]) ? path[3] : null;
    }

    private String clientIp(HttpServletRequest request) {
        String forwarded = request.getHeader("X-Forwarded-For");
        return forwarded == null || forwarded.isBlank() ? request.getRemoteAddr() : forwarded.split(",", 2)[0].trim();
    }
}
