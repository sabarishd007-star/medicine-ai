package com.mediscan.backend.medibridge;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.mediscan.backend.medibridge.dto.ResourceDtos.ResourceView;
import com.mediscan.backend.medibridge.dto.ResourceDtos.StatusUpdateRequest;
import com.mediscan.backend.medibridge.model.ResourceStatus;
import com.mediscan.backend.medibridge.model.ResourceType;
import com.mediscan.backend.medibridge.service.ResourceService;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.web.server.ResponseStatusException;

@SpringBootTest
class ResourceServiceTest {

    @Autowired
    private ResourceService service;

    private static final double CHENNAI_LAT = 13.0604;
    private static final double CHENNAI_LNG = 80.2496;

    @Test
    @DisplayName("haversine matches a known distance")
    void haversineIsAccurate() {
        // Chennai -> Bengaluru is roughly 290 km great-circle.
        double km = ResourceService.haversineKm(13.0827, 80.2707, 12.9716, 77.5946);
        assertThat(km).isBetween(280.0, 300.0);

        assertThat(ResourceService.haversineKm(13.0, 80.0, 13.0, 80.0)).isZero();
    }

    @Test
    @DisplayName("seed data loaded")
    void seedDataPresent() {
        assertThat(service.findAll(null)).hasSizeGreaterThanOrEqualTo(15);
    }

    @Test
    @DisplayName("nearby results are inside the radius and sorted by distance")
    void nearbyRespectsRadiusAndOrder() {
        List<ResourceView> results = service.findNearby(CHENNAI_LAT, CHENNAI_LNG, 10.0, null);

        assertThat(results).isNotEmpty();
        assertThat(results).allSatisfy(view -> assertThat(view.distanceKm()).isLessThanOrEqualTo(10.0));
        assertThat(results)
                .extracting(ResourceView::distanceKm)
                .isSortedAccordingTo(Double::compareTo);
    }

    @Test
    @DisplayName("a tiny radius excludes far resources")
    void tightRadiusFilters() {
        List<ResourceView> wide = service.findNearby(CHENNAI_LAT, CHENNAI_LNG, 50.0, null);
        List<ResourceView> tight = service.findNearby(CHENNAI_LAT, CHENNAI_LNG, 1.0, null);
        assertThat(tight.size()).isLessThan(wide.size());
    }

    @Test
    @DisplayName("type filter returns only that type")
    void filtersByType() {
        List<ResourceView> ambulances =
                service.findNearby(CHENNAI_LAT, CHENNAI_LNG, 50.0, ResourceType.AMBULANCE);
        assertThat(ambulances).isNotEmpty();
        assertThat(ambulances).allSatisfy(v -> assertThat(v.type()).isEqualTo(ResourceType.AMBULANCE));
    }

    @Test
    @DisplayName("invalid coordinates and radius are rejected")
    void validatesInput() {
        assertThatThrownBy(() -> service.findNearby(200, 80, 10.0, null))
                .isInstanceOf(ResponseStatusException.class);
        assertThatThrownBy(() -> service.findNearby(13, 400, 10.0, null))
                .isInstanceOf(ResponseStatusException.class);
        assertThatThrownBy(() -> service.findNearby(13, 80, -5.0, null))
                .isInstanceOf(ResponseStatusException.class);
        assertThatThrownBy(() -> service.findNearby(13, 80, 5000.0, null))
                .isInstanceOf(ResponseStatusException.class);
    }

    @Test
    @DisplayName("ambulance toggle keeps headline status consistent with the dispatch flag")
    void ambulanceStatusStaysConsistent() {
        ResourceView ambulance =
                service.findNearby(CHENNAI_LAT, CHENNAI_LNG, 50.0, ResourceType.AMBULANCE).get(0);

        ResourceView busy = service.updateStatus(
                ambulance.id(),
                new StatusUpdateRequest(null, null, false, "On call", null, null, null));
        assertThat(busy.ambulance().available()).isFalse();
        assertThat(busy.status()).isEqualTo(ResourceStatus.BUSY);

        ResourceView free = service.updateStatus(
                ambulance.id(),
                new StatusUpdateRequest(null, null, true, "Back at base", null, null, null));
        assertThat(free.ambulance().available()).isTrue();
        assertThat(free.status()).isEqualTo(ResourceStatus.AVAILABLE);
    }

    @Test
    @DisplayName("blood stock updates in place rather than duplicating a group")
    void bloodStockUpdatesInPlace() {
        ResourceView bank =
                service.findNearby(CHENNAI_LAT, CHENNAI_LNG, 50.0, ResourceType.BLOOD_BANK).get(0);
        int groupsBefore = bank.bloodInventory().size();

        String group = bank.bloodInventory().get(0).bloodGroup();
        ResourceView updated = service.updateStatus(
                bank.id(), new StatusUpdateRequest(null, null, null, null, group, 42, null));

        assertThat(updated.bloodInventory()).hasSize(groupsBefore);
        assertThat(updated.bloodInventory())
                .filteredOn(stock -> stock.bloodGroup().equals(group))
                .singleElement()
                .satisfies(stock -> assertThat(stock.unitsAvailable()).isEqualTo(42));
    }

    @Test
    @DisplayName("capacity cannot exceed the total or go negative")
    void rejectsImpossibleCapacity() {
        ResourceView hospital =
                service.findNearby(CHENNAI_LAT, CHENNAI_LNG, 50.0, ResourceType.HOSPITAL).get(0);

        assertThatThrownBy(() -> service.updateStatus(
                        hospital.id(),
                        new StatusUpdateRequest(null, 99_999, null, null, null, null, null)))
                .isInstanceOf(ResponseStatusException.class);

        assertThatThrownBy(() -> service.updateStatus(
                        hospital.id(),
                        new StatusUpdateRequest(null, -1, null, null, null, null, null)))
                .isInstanceOf(ResponseStatusException.class);
    }

    @Test
    @DisplayName("ambulance fields are rejected on a non-ambulance resource")
    void rejectsMismatchedResourceType() {
        ResourceView pharmacy =
                service.findNearby(CHENNAI_LAT, CHENNAI_LNG, 50.0, ResourceType.PHARMACY).get(0);

        assertThatThrownBy(() -> service.updateStatus(
                        pharmacy.id(),
                        new StatusUpdateRequest(null, null, true, null, null, null, null)))
                .isInstanceOf(ResponseStatusException.class);

        assertThatThrownBy(() -> service.updateStatus(
                        pharmacy.id(),
                        new StatusUpdateRequest(null, null, null, null, "O+", 5, null)))
                .isInstanceOf(ResponseStatusException.class);
    }

    @Test
    @DisplayName("unknown resource id is a 404, not a crash")
    void unknownIdIsNotFound() {
        assertThatThrownBy(() -> service.findOne(999_999L))
                .isInstanceOf(ResponseStatusException.class);
    }
}
