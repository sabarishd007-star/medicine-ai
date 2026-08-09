package com.mediscan.backend.medibridge.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.OneToOne;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import java.time.Instant;

/**
 * Live dispatch state for one ambulance.
 *
 * <p>Ambulances move, so the current position is tracked here rather than on
 * the parent {@link Resource}, whose lat/lng is its home station.
 */
@Entity
@Table(name = "ambulance_status")
public class AmbulanceStatus {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @OneToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "resource_id", nullable = false, unique = true)
    private Resource resource;

    @Column(nullable = false)
    private Boolean available = true;

    /** Human-readable location label, e.g. "Anna Salai / Mount Road". */
    @Column(length = 160)
    private String currentLocation;

    private Double currentLatitude;

    private Double currentLongitude;

    @Column(length = 32)
    private String vehicleType;

    @Column(nullable = false)
    private Instant lastUpdated = Instant.now();

    protected AmbulanceStatus() {
    }

    public AmbulanceStatus(Resource resource, Boolean available, String currentLocation) {
        this.resource = resource;
        this.available = available;
        this.currentLocation = currentLocation;
        this.currentLatitude = resource.getLatitude();
        this.currentLongitude = resource.getLongitude();
    }

    @PreUpdate
    void touch() {
        this.lastUpdated = Instant.now();
    }

    public Long getId() {
        return id;
    }

    public Resource getResource() {
        return resource;
    }

    public void setResource(Resource resource) {
        this.resource = resource;
    }

    public Boolean getAvailable() {
        return available;
    }

    public void setAvailable(Boolean available) {
        this.available = available;
        this.lastUpdated = Instant.now();
    }

    public String getCurrentLocation() {
        return currentLocation;
    }

    public void setCurrentLocation(String currentLocation) {
        this.currentLocation = currentLocation;
    }

    public Double getCurrentLatitude() {
        return currentLatitude;
    }

    public void setCurrentLatitude(Double currentLatitude) {
        this.currentLatitude = currentLatitude;
    }

    public Double getCurrentLongitude() {
        return currentLongitude;
    }

    public void setCurrentLongitude(Double currentLongitude) {
        this.currentLongitude = currentLongitude;
    }

    public String getVehicleType() {
        return vehicleType;
    }

    public void setVehicleType(String vehicleType) {
        this.vehicleType = vehicleType;
    }

    public Instant getLastUpdated() {
        return lastUpdated;
    }
}
