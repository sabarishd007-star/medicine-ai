package com.mediscan.backend.medibridge.dto;

import com.mediscan.backend.medibridge.model.AmbulanceStatus;
import com.mediscan.backend.medibridge.model.BloodInventory;
import com.mediscan.backend.medibridge.model.Resource;
import com.mediscan.backend.medibridge.model.ResourceStatus;
import com.mediscan.backend.medibridge.model.ResourceType;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import java.time.Instant;
import java.util.List;

public final class ResourceDtos {

    private ResourceDtos() {
    }

    public record BloodStock(String bloodGroup, Integer unitsAvailable, Instant lastUpdated) {
        public static BloodStock from(BloodInventory entry) {
            return new BloodStock(
                    entry.getBloodGroup(), entry.getUnitsAvailable(), entry.getLastUpdated());
        }
    }

    public record AmbulanceInfo(
            Boolean available,
            String currentLocation,
            String vehicleType,
            Instant lastUpdated) {
        public static AmbulanceInfo from(AmbulanceStatus status) {
            return new AmbulanceInfo(
                    status.getAvailable(),
                    status.getCurrentLocation(),
                    status.getVehicleType(),
                    status.getLastUpdated());
        }
    }

    /**
     * A resource as shown on a card. {@code distanceKm} is null when the caller
     * did not supply a location, rather than 0, so the UI never renders a
     * misleading "0.0 km away".
     */
    public record ResourceView(
            Long id,
            ResourceType type,
            String name,
            String address,
            Double latitude,
            Double longitude,
            String contactNumber,
            ResourceStatus status,
            String notes,
            Integer capacityTotal,
            Integer capacityAvailable,
            Double distanceKm,
            Boolean stale,
            Instant lastUpdated,
            List<BloodStock> bloodInventory,
            AmbulanceInfo ambulance) {

        public static ResourceView from(Resource resource, Double distanceKm, boolean stale) {
            return new ResourceView(
                    resource.getId(),
                    resource.getType(),
                    resource.getName(),
                    resource.getAddress(),
                    resource.getLatitude(),
                    resource.getLongitude(),
                    resource.getContactNumber(),
                    resource.getStatus(),
                    resource.getNotes(),
                    resource.getCapacityTotal(),
                    resource.getCapacityAvailable(),
                    distanceKm,
                    stale,
                    resource.getLastUpdated(),
                    resource.getBloodInventory().stream().map(BloodStock::from).toList(),
                    resource.getAmbulanceStatus() == null
                            ? null
                            : AmbulanceInfo.from(resource.getAmbulanceStatus()));
        }
    }

    /** Admin update: every field is optional so a caller can change one thing. */
    public record StatusUpdateRequest(
            ResourceStatus status,
            Integer capacityAvailable,
            Boolean ambulanceAvailable,
            String ambulanceLocation,
            String bloodGroup,
            @Min(0) @Max(10_000) Integer unitsAvailable,
            String notes) {
    }

    public record NearbyQuery(
            @NotNull Double lat,
            @NotNull Double lng,
            Double radiusKm,
            ResourceType type) {
    }

    /** Payload broadcast over WebSocket whenever a resource changes. */
    public record ResourceUpdateEvent(
            String event, Long resourceId, ResourceView resource, Instant at) {

        public static ResourceUpdateEvent of(ResourceView view) {
            return new ResourceUpdateEvent("RESOURCE_UPDATED", view.id(), view, Instant.now());
        }
    }
}
