package com.mediscan.backend.medibridge.service;

import com.mediscan.backend.medibridge.dto.ResourceDtos.ResourceUpdateEvent;
import com.mediscan.backend.medibridge.dto.ResourceDtos.ResourceView;
import com.mediscan.backend.medibridge.dto.ResourceDtos.StatusUpdateRequest;
import com.mediscan.backend.medibridge.model.AmbulanceStatus;
import com.mediscan.backend.medibridge.model.BloodInventory;
import com.mediscan.backend.medibridge.model.Resource;
import com.mediscan.backend.medibridge.model.ResourceStatus;
import com.mediscan.backend.medibridge.model.ResourceType;
import com.mediscan.backend.medibridge.repository.BloodInventoryRepository;
import com.mediscan.backend.medibridge.repository.ResourceRepository;
import java.time.Duration;
import java.time.Instant;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import org.springframework.http.HttpStatus;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

@Service
public class ResourceService {

    /** Earth mean radius, kilometres. */
    private static final double EARTH_RADIUS_KM = 6371.0088;

    private static final double DEFAULT_RADIUS_KM = 10.0;
    private static final double MAX_RADIUS_KM = 200.0;

    /**
     * A status older than this is reported as stale. In an emergency network a
     * six-hour-old "beds available" reading is not evidence of anything, and
     * the UI must be able to say so instead of showing it as current.
     */
    private static final Duration STALE_AFTER = Duration.ofMinutes(30);

    public static final String TOPIC = "/topic/resources";

    private final ResourceRepository resources;
    private final BloodInventoryRepository bloodInventory;
    private final SimpMessagingTemplate broker;

    public ResourceService(
            ResourceRepository resources,
            BloodInventoryRepository bloodInventory,
            SimpMessagingTemplate broker) {
        this.resources = resources;
        this.bloodInventory = bloodInventory;
        this.broker = broker;
    }

    /** Great-circle distance in kilometres. */
    public static double haversineKm(double lat1, double lng1, double lat2, double lng2) {
        double dLat = Math.toRadians(lat2 - lat1);
        double dLng = Math.toRadians(lng2 - lng1);
        double a = Math.sin(dLat / 2) * Math.sin(dLat / 2)
                + Math.cos(Math.toRadians(lat1))
                        * Math.cos(Math.toRadians(lat2))
                        * Math.sin(dLng / 2)
                        * Math.sin(dLng / 2);
        return 2 * EARTH_RADIUS_KM * Math.asin(Math.min(1.0, Math.sqrt(a)));
    }

    private static boolean isStale(Resource resource) {
        return resource.getLastUpdated().isBefore(Instant.now().minus(STALE_AFTER));
    }

    @Transactional(readOnly = true)
    public List<ResourceView> findNearby(
            double lat, double lng, Double radiusKmRaw, ResourceType type) {

        if (lat < -90 || lat > 90 || lng < -180 || lng > 180) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST, "Latitude or longitude is out of range.");
        }
        double radiusKm = radiusKmRaw == null ? DEFAULT_RADIUS_KM : radiusKmRaw;
        if (radiusKm <= 0 || radiusKm > MAX_RADIUS_KM) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST, "Radius must be between 0 and " + MAX_RADIUS_KM + " km.");
        }

        // Degrees of latitude are ~constant; degrees of longitude shrink with
        // latitude, so the box must be widened by 1/cos(lat) to avoid clipping
        // results near the poles.
        double latDelta = Math.toDegrees(radiusKm / EARTH_RADIUS_KM);
        double cosLat = Math.cos(Math.toRadians(lat));
        double lngDelta = Math.abs(cosLat) < 1e-6
                ? 180.0
                : Math.toDegrees(radiusKm / (EARTH_RADIUS_KM * Math.abs(cosLat)));

        List<Resource> candidates = (type == null)
                ? resources.findWithinBox(
                        lat - latDelta, lat + latDelta, lng - lngDelta, lng + lngDelta)
                : resources.findWithinBoxByType(
                        type, lat - latDelta, lat + latDelta, lng - lngDelta, lng + lngDelta);

        return candidates.stream()
                .map(resource -> {
                    double distance = haversineKm(
                            lat, lng, resource.getLatitude(), resource.getLongitude());
                    return ResourceView.from(resource, round(distance), isStale(resource));
                })
                .filter(view -> view.distanceKm() <= radiusKm)
                .sorted(Comparator.comparingDouble(ResourceView::distanceKm))
                .toList();
    }

    @Transactional(readOnly = true)
    public List<ResourceView> findAll(ResourceType type) {
        List<Resource> rows = (type == null) ? resources.findAll() : resources.findByType(type);
        return rows.stream()
                .map(resource -> ResourceView.from(resource, null, isStale(resource)))
                .sorted(Comparator.comparing(ResourceView::name))
                .toList();
    }

    @Transactional(readOnly = true)
    public ResourceView findOne(Long id) {
        Resource resource = resources.findById(id).orElseThrow(() ->
                new ResponseStatusException(HttpStatus.NOT_FOUND, "Resource not found."));
        return ResourceView.from(resource, null, isStale(resource));
    }

    /**
     * Applies an admin status change and broadcasts it to every subscriber.
     * The broadcast is what makes the network "live": one staff update reaches
     * all open clients without them polling.
     */
    @Transactional
    public ResourceView updateStatus(Long id, StatusUpdateRequest request) {
        Resource resource = resources.findById(id).orElseThrow(() ->
                new ResponseStatusException(HttpStatus.NOT_FOUND, "Resource not found."));

        if (request.status() != null) {
            resource.setStatus(request.status());
        }
        if (request.notes() != null) {
            resource.setNotes(request.notes());
        }
        if (request.capacityAvailable() != null) {
            int available = request.capacityAvailable();
            if (available < 0) {
                throw new ResponseStatusException(
                        HttpStatus.BAD_REQUEST, "Capacity cannot be negative.");
            }
            if (resource.getCapacityTotal() != null && available > resource.getCapacityTotal()) {
                throw new ResponseStatusException(
                        HttpStatus.BAD_REQUEST,
                        "Available capacity cannot exceed total capacity ("
                                + resource.getCapacityTotal() + ").");
            }
            resource.setCapacityAvailable(available);
        }

        applyAmbulanceUpdate(resource, request);
        applyBloodUpdate(resource, request);

        resource.setLastUpdated(Instant.now());
        resources.save(resource);

        ResourceView view = ResourceView.from(resource, null, false);
        broker.convertAndSend(TOPIC, ResourceUpdateEvent.of(view));
        return view;
    }

    private void applyAmbulanceUpdate(Resource resource, StatusUpdateRequest request) {
        if (request.ambulanceAvailable() == null && request.ambulanceLocation() == null) {
            return;
        }
        if (resource.getType() != ResourceType.AMBULANCE) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST, "This resource is not an ambulance.");
        }

        AmbulanceStatus status = resource.getAmbulanceStatus();
        if (status == null) {
            status = new AmbulanceStatus(resource, true, null);
            resource.setAmbulanceStatus(status);
        }
        if (request.ambulanceAvailable() != null) {
            status.setAvailable(request.ambulanceAvailable());
            // Keep the headline status consistent with the dispatch flag, so a
            // card can never read "Available" while the ambulance is on a call.
            resource.setStatus(
                    request.ambulanceAvailable() ? ResourceStatus.AVAILABLE : ResourceStatus.BUSY);
        }
        if (request.ambulanceLocation() != null) {
            status.setCurrentLocation(request.ambulanceLocation());
        }
    }

    private void applyBloodUpdate(Resource resource, StatusUpdateRequest request) {
        if (request.bloodGroup() == null || request.unitsAvailable() == null) {
            return;
        }
        if (resource.getType() != ResourceType.BLOOD_BANK
                && resource.getType() != ResourceType.HOSPITAL) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST, "This resource does not hold blood stock.");
        }

        String group = request.bloodGroup().trim().toUpperCase(Locale.ROOT);
        BloodInventory entry = bloodInventory
                .findByResourceIdAndBloodGroupIgnoreCase(resource.getId(), group)
                .orElse(null);

        if (entry == null) {
            BloodInventory created = new BloodInventory(group, request.unitsAvailable());
            resource.addBloodInventory(created);
        } else {
            entry.setUnitsAvailable(request.unitsAvailable());
            bloodInventory.save(entry);
        }
    }

    private static double round(double value) {
        return Math.round(value * 100.0) / 100.0;
    }
}
