package com.mediscan.backend.medibridge.repository;

import com.mediscan.backend.medibridge.model.BloodInventory;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface BloodInventoryRepository extends JpaRepository<BloodInventory, Long> {

    List<BloodInventory> findByResourceId(Long resourceId);

    Optional<BloodInventory> findByResourceIdAndBloodGroupIgnoreCase(
            Long resourceId, String bloodGroup);
}
