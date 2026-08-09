package com.mediscan.backend.repository;

import com.mediscan.backend.model.Scan;
import com.mediscan.backend.model.User;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ScanRepository extends JpaRepository<Scan, Long> {

    List<Scan> findByUserOrderByCreatedAtDesc(User user);

    Optional<Scan> findByIdAndUser(Long id, User user);

    long countByUser(User user);
}
