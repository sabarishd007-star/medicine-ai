package com.mediscan.backend.medibridge.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import java.time.Instant;

/**
 * Units of one blood group held by one blood bank.
 *
 * <p>The unique constraint on (resource, bloodGroup) prevents duplicate rows
 * for the same group at the same bank, which would otherwise let two admin
 * updates disagree about stock.
 */
@Entity
@Table(
        name = "blood_inventory",
        uniqueConstraints =
                @UniqueConstraint(
                        name = "uk_blood_resource_group",
                        columnNames = {"resource_id", "blood_group"}))
public class BloodInventory {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "resource_id", nullable = false)
    private Resource resource;

    @Column(name = "blood_group", nullable = false, length = 8)
    private String bloodGroup;

    @Column(nullable = false)
    private Integer unitsAvailable = 0;

    @Column(nullable = false)
    private Instant lastUpdated = Instant.now();

    protected BloodInventory() {
    }

    public BloodInventory(String bloodGroup, Integer unitsAvailable) {
        this.bloodGroup = bloodGroup;
        this.unitsAvailable = unitsAvailable;
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

    public String getBloodGroup() {
        return bloodGroup;
    }

    public Integer getUnitsAvailable() {
        return unitsAvailable;
    }

    public void setUnitsAvailable(Integer unitsAvailable) {
        this.unitsAvailable = unitsAvailable;
        this.lastUpdated = Instant.now();
    }

    public Instant getLastUpdated() {
        return lastUpdated;
    }
}
