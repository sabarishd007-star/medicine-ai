package com.mediscan.backend.medibridge.model;

/**
 * Operational status of a resource.
 *
 * <p>UNKNOWN exists deliberately and is the default. In an emergency tool,
 * "we do not know" is a real and useful answer; silently defaulting a stale
 * record to OPEN would send someone to a closed pharmacy.
 */
public enum ResourceStatus {
    OPEN,
    CLOSED,
    FULL,
    LIMITED,
    AVAILABLE,
    BUSY,
    UNKNOWN
}
