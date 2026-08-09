package com.mediscan.backend.medibridge.repository;

import com.mediscan.backend.medibridge.model.AmbulanceStatus;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AmbulanceStatusRepository extends JpaRepository<AmbulanceStatus, Long> {

    Optional<AmbulanceStatus> findByResourceId(Long resourceId);
}
