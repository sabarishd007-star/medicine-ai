package com.mediscan.backend.medibridge.repository;

import com.mediscan.backend.medibridge.model.Resource;
import com.mediscan.backend.medibridge.model.ResourceType;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface ResourceRepository extends JpaRepository<Resource, Long> {

    List<Resource> findByType(ResourceType type);

    /**
     * Coarse bounding-box prefilter. This is intentionally a box, not a circle:
     * it is index-friendly and portable across H2 and MySQL. The service then
     * applies exact haversine distance, so the final result set is a true
     * radius search - the box only limits how many rows Java has to measure.
     */
    @Query("""
            SELECT r FROM Resource r
            WHERE r.latitude BETWEEN :minLat AND :maxLat
              AND r.longitude BETWEEN :minLng AND :maxLng
            """)
    List<Resource> findWithinBox(
            @Param("minLat") double minLat,
            @Param("maxLat") double maxLat,
            @Param("minLng") double minLng,
            @Param("maxLng") double maxLng);

    @Query("""
            SELECT r FROM Resource r
            WHERE r.type = :type
              AND r.latitude BETWEEN :minLat AND :maxLat
              AND r.longitude BETWEEN :minLng AND :maxLng
            """)
    List<Resource> findWithinBoxByType(
            @Param("type") ResourceType type,
            @Param("minLat") double minLat,
            @Param("maxLat") double maxLat,
            @Param("minLng") double minLng,
            @Param("maxLng") double maxLng);
}
