package com.mediscan.backend.medibridge.controller;

import com.mediscan.backend.medibridge.dto.ResourceDtos.ResourceView;
import com.mediscan.backend.medibridge.dto.ResourceDtos.StatusUpdateRequest;
import com.mediscan.backend.medibridge.model.ResourceType;
import com.mediscan.backend.medibridge.service.ResourceService;
import jakarta.validation.Valid;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * MediBridge REST API.
 *
 * <p>Reads are public: someone in an emergency must not be blocked by a login
 * screen. Writes go through {@code /admin/**}, which the security config
 * requires authentication for, since a status change affects every user.
 */
@RestController
@RequestMapping("/api/medibridge")
public class ResourceController {

    private final ResourceService service;

    public ResourceController(ResourceService service) {
        this.service = service;
    }

    /** Nearby resources sorted by true distance. */
    @GetMapping("/resources/nearby")
    public ResponseEntity<List<ResourceView>> nearby(
            @RequestParam double lat,
            @RequestParam double lng,
            @RequestParam(required = false) Double radiusKm,
            @RequestParam(required = false) ResourceType type) {
        return ResponseEntity.ok(service.findNearby(lat, lng, radiusKm, type));
    }

    /** Full catalogue, used when the browser denies geolocation. */
    @GetMapping("/resources")
    public ResponseEntity<List<ResourceView>> all(
            @RequestParam(required = false) ResourceType type) {
        return ResponseEntity.ok(service.findAll(type));
    }

    @GetMapping("/resources/{id}")
    public ResponseEntity<ResourceView> one(@PathVariable Long id) {
        return ResponseEntity.ok(service.findOne(id));
    }

    @GetMapping("/types")
    public ResponseEntity<List<String>> types() {
        return ResponseEntity.ok(java.util.Arrays.stream(ResourceType.values()).map(Enum::name).toList());
    }

    /**
     * Polling fallback. The React client prefers the WebSocket topic; this
     * endpoint exists so the feature still demos if sockets are unavailable.
     */
    @GetMapping("/resources/live")
    public ResponseEntity<Map<String, Object>> live(
            @RequestParam(required = false) Double lat,
            @RequestParam(required = false) Double lng,
            @RequestParam(required = false) Double radiusKm,
            @RequestParam(required = false) ResourceType type) {

        List<ResourceView> data = (lat == null || lng == null)
                ? service.findAll(type)
                : service.findNearby(lat, lng, radiusKm, type);
        return ResponseEntity.ok(Map.of("at", Instant.now().toString(), "resources", data));
    }

    /** Simulates hospital staff updating availability. Requires auth. */
    @PostMapping("/admin/resources/{id}/status")
    public ResponseEntity<ResourceView> updateStatus(
            @PathVariable Long id, @Valid @RequestBody StatusUpdateRequest request) {
        return ResponseEntity.ok(service.updateStatus(id, request));
    }
}
