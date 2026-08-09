package com.mediscan.backend.medibridge.service;

import com.mediscan.backend.medibridge.model.AmbulanceStatus;
import com.mediscan.backend.medibridge.model.BloodInventory;
import com.mediscan.backend.medibridge.model.Resource;
import com.mediscan.backend.medibridge.model.ResourceStatus;
import com.mediscan.backend.medibridge.model.ResourceType;
import com.mediscan.backend.medibridge.repository.ResourceRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Seeds demo resources around Chennai on first start.
 *
 * <p>These are illustrative records for a demo, not a verified directory.
 * Coordinates are approximate and the availability numbers are invented, which
 * is why every resource carries a demo flag in its notes - nobody should read
 * these as real emergency capacity.
 */
@Configuration
public class ResourceSeeder {

    private static final Logger log = LoggerFactory.getLogger(ResourceSeeder.class);
    private static final String DEMO = "Demo data - not a verified live feed.";

    @Bean
    ApplicationRunner seedResources(ResourceRepository resources) {
        return args -> {
            if (resources.count() > 0) {
                return;
            }

            // --- Hospitals & emergency departments -------------------------
            Resource apollo = hospital(
                    "Apollo Hospitals, Greams Road", 13.0604, 80.2496, "+91-44-2829-3333",
                    ResourceStatus.OPEN, 60, 12, "Multi-speciality, 24x7 emergency");
            Resource rajiv = hospital(
                    "Rajiv Gandhi Government General Hospital", 13.0836, 80.2750,
                    "+91-44-2530-5000", ResourceStatus.LIMITED, 120, 8,
                    "Government tertiary care, trauma centre");
            Resource kauvery = hospital(
                    "Kauvery Hospital, Alwarpet", 13.0339, 80.2536, "+91-44-4000-6000",
                    ResourceStatus.OPEN, 40, 15, "24x7 emergency and cardiac care");
            Resource fortis = hospital(
                    "Fortis Malar Hospital, Adyar", 13.0067, 80.2571, "+91-44-4289-2222",
                    ResourceStatus.FULL, 35, 0, "Emergency department at capacity");

            Resource stanleyEd = resource(
                    ResourceType.EMERGENCY_DEPARTMENT, "Stanley Medical College - Emergency",
                    13.1067, 80.2847, "+91-44-2528-1351", ResourceStatus.OPEN,
                    "Casualty and trauma intake", 45, 9);
            Resource miotEd = resource(
                    ResourceType.EMERGENCY_DEPARTMENT, "MIOT International - Emergency",
                    13.0155, 80.1875, "+91-44-4200-2288", ResourceStatus.LIMITED,
                    "Accident and emergency wing", 30, 3);

            // --- Blood banks -----------------------------------------------
            Resource redCross = resource(
                    ResourceType.BLOOD_BANK, "Indian Red Cross Society Blood Bank",
                    13.0632, 80.2707, "+91-44-2819-1027", ResourceStatus.OPEN,
                    "Voluntary donation centre", null, null);
            redCross.addBloodInventory(new BloodInventory("O+", 24));
            redCross.addBloodInventory(new BloodInventory("O-", 6));
            redCross.addBloodInventory(new BloodInventory("A+", 18));
            redCross.addBloodInventory(new BloodInventory("B+", 15));
            redCross.addBloodInventory(new BloodInventory("AB+", 4));

            Resource jeevan = resource(
                    ResourceType.BLOOD_BANK, "Jeevan Blood Bank & Research Centre",
                    13.0410, 80.2340, "+91-44-2432-4441", ResourceStatus.OPEN,
                    "Component separation facility", null, null);
            jeevan.addBloodInventory(new BloodInventory("O+", 31));
            jeevan.addBloodInventory(new BloodInventory("O-", 2));
            jeevan.addBloodInventory(new BloodInventory("A-", 5));
            jeevan.addBloodInventory(new BloodInventory("B+", 22));

            apollo.addBloodInventory(new BloodInventory("O+", 9));
            apollo.addBloodInventory(new BloodInventory("AB-", 1));

            // --- Ambulances -------------------------------------------------
            Resource amb1 = resource(
                    ResourceType.AMBULANCE, "108 Ambulance - Unit 12", 13.0569, 80.2425,
                    "108", ResourceStatus.AVAILABLE, "Advanced life support", null, null);
            Resource amb2 = resource(
                    ResourceType.AMBULANCE, "108 Ambulance - Unit 27", 13.0878, 80.2785,
                    "108", ResourceStatus.BUSY, "Basic life support", null, null);
            Resource amb3 = resource(
                    ResourceType.AMBULANCE, "Apollo Ambulance - AMB 04", 13.0301, 80.2489,
                    "+91-44-2829-0200", ResourceStatus.AVAILABLE, "Cardiac ambulance",
                    null, null);
            Resource amb4 = resource(
                    ResourceType.AMBULANCE, "GVK EMRI - Unit 41", 13.0122, 80.2201,
                    "108", ResourceStatus.AVAILABLE, "Patient transport", null, null);

            // --- Pharmacies --------------------------------------------------
            Resource pharm1 = resource(
                    ResourceType.PHARMACY, "Apollo Pharmacy, Nungambakkam", 13.0592, 80.2417,
                    "+91-44-2833-4455", ResourceStatus.OPEN, "24 hours", null, null);
            Resource pharm2 = resource(
                    ResourceType.PHARMACY, "MedPlus, T. Nagar", 13.0418, 80.2341,
                    "+91-44-2815-6677", ResourceStatus.OPEN, "08:00 - 23:00", null, null);
            Resource pharm3 = resource(
                    ResourceType.PHARMACY, "Wellness Forever, Adyar", 13.0012, 80.2565,
                    "+91-44-2440-9988", ResourceStatus.CLOSED, "Opens 07:00", null, null);

            // --- Shelters -----------------------------------------------------
            Resource shelter1 = resource(
                    ResourceType.SHELTER, "Corporation Relief Shelter, Kotturpuram",
                    13.0180, 80.2430, "+91-44-2591-1000", ResourceStatus.OPEN,
                    "Flood relief shelter", 200, 145);
            Resource shelter2 = resource(
                    ResourceType.SHELTER, "Community Shelter, Perambur", 13.1140, 80.2330,
                    "+91-44-2670-4321", ResourceStatus.LIMITED, "Night shelter", 80, 6);

            resources.saveAll(java.util.List.of(
                    apollo, rajiv, kauvery, fortis, stanleyEd, miotEd,
                    redCross, jeevan,
                    amb1, amb2, amb3, amb4,
                    pharm1, pharm2, pharm3,
                    shelter1, shelter2));

            attachAmbulance(resources, amb1, true, "Nungambakkam High Road", "ALS");
            attachAmbulance(resources, amb2, false, "En route to RGGGH", "BLS");
            attachAmbulance(resources, amb3, true, "Alwarpet Junction", "Cardiac");
            attachAmbulance(resources, amb4, true, "Guindy Industrial Estate", "PTS");

            log.info("MediBridge: seeded {} demo emergency resources", resources.count());
        };
    }

    private static void attachAmbulance(
            ResourceRepository repository,
            Resource resource,
            boolean available,
            String location,
            String vehicleType) {
        AmbulanceStatus status = new AmbulanceStatus(resource, available, location);
        status.setVehicleType(vehicleType);
        resource.setAmbulanceStatus(status);
        repository.save(resource);
    }

    private static Resource hospital(
            String name, double lat, double lng, String phone,
            ResourceStatus status, Integer total, Integer available, String notes) {
        return resource(ResourceType.HOSPITAL, name, lat, lng, phone, status, notes, total, available);
    }

    private static Resource resource(
            ResourceType type, String name, double lat, double lng, String phone,
            ResourceStatus status, String notes, Integer total, Integer available) {
        Resource resource = new Resource(type, name, lat, lng, phone);
        resource.setStatus(status);
        resource.setNotes(notes == null ? DEMO : notes + " - " + DEMO);
        resource.setCapacityTotal(total);
        resource.setCapacityAvailable(available);
        return resource;
    }
}
