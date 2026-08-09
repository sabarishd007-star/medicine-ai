package com.mediscan.backend.medibridge.model;

import jakarta.persistence.CascadeType;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.OneToMany;
import jakarta.persistence.OneToOne;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

/**
 * A single emergency resource: hospital, pharmacy, blood bank, ambulance or
 * shelter.
 *
 * <p>Latitude/longitude are stored as plain columns rather than a spatial type
 * so the schema works identically on H2 and MySQL. The radius search bounds the
 * query with a cheap lat/lng box in SQL, then applies exact haversine distance
 * in Java. At the scale this module targets that is far simpler than requiring
 * spatial extensions, and the correctness is identical.
 *
 * <p>{@code capacityTotal}/{@code capacityAvailable} are nullable on purpose:
 * a pharmacy has no bed count, and reporting a fabricated zero would be worse
 * than reporting nothing.
 */
@Entity
@Table(
        name = "resources",
        indexes = {
            @Index(name = "idx_resource_type", columnList = "type"),
            @Index(name = "idx_resource_geo", columnList = "latitude,longitude")
        })
public class Resource {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 32)
    private ResourceType type;

    @Column(nullable = false, length = 160)
    private String name;

    @Column(length = 255)
    private String address;

    @Column(nullable = false)
    private Double latitude;

    @Column(nullable = false)
    private Double longitude;

    @Column(length = 32)
    private String contactNumber;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 32)
    private ResourceStatus status = ResourceStatus.UNKNOWN;

    /** Free-text detail shown on the card, e.g. "Level 1 trauma centre". */
    @Column(length = 255)
    private String notes;

    private Integer capacityTotal;

    private Integer capacityAvailable;

    @Column(nullable = false)
    private Instant lastUpdated = Instant.now();

    @OneToMany(mappedBy = "resource", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<BloodInventory> bloodInventory = new ArrayList<>();

    @OneToOne(mappedBy = "resource", cascade = CascadeType.ALL, orphanRemoval = true)
    private AmbulanceStatus ambulanceStatus;

    protected Resource() {
    }

    public Resource(
            ResourceType type, String name, Double latitude, Double longitude, String contactNumber) {
        this.type = type;
        this.name = name;
        this.latitude = latitude;
        this.longitude = longitude;
        this.contactNumber = contactNumber;
    }

    @PreUpdate
    void touch() {
        this.lastUpdated = Instant.now();
    }

    public Long getId() {
        return id;
    }

    public ResourceType getType() {
        return type;
    }

    public String getName() {
        return name;
    }

    public String getAddress() {
        return address;
    }

    public void setAddress(String address) {
        this.address = address;
    }

    public Double getLatitude() {
        return latitude;
    }

    public Double getLongitude() {
        return longitude;
    }

    public String getContactNumber() {
        return contactNumber;
    }

    public ResourceStatus getStatus() {
        return status;
    }

    public void setStatus(ResourceStatus status) {
        this.status = status;
    }

    public String getNotes() {
        return notes;
    }

    public void setNotes(String notes) {
        this.notes = notes;
    }

    public Integer getCapacityTotal() {
        return capacityTotal;
    }

    public void setCapacityTotal(Integer capacityTotal) {
        this.capacityTotal = capacityTotal;
    }

    public Integer getCapacityAvailable() {
        return capacityAvailable;
    }

    public void setCapacityAvailable(Integer capacityAvailable) {
        this.capacityAvailable = capacityAvailable;
    }

    public Instant getLastUpdated() {
        return lastUpdated;
    }

    public void setLastUpdated(Instant lastUpdated) {
        this.lastUpdated = lastUpdated;
    }

    public List<BloodInventory> getBloodInventory() {
        return bloodInventory;
    }

    public AmbulanceStatus getAmbulanceStatus() {
        return ambulanceStatus;
    }

    public void setAmbulanceStatus(AmbulanceStatus ambulanceStatus) {
        this.ambulanceStatus = ambulanceStatus;
    }

    public void addBloodInventory(BloodInventory entry) {
        entry.setResource(this);
        this.bloodInventory.add(entry);
    }
}
