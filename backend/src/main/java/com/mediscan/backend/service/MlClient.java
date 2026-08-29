package com.mediscan.backend.service;

import java.time.Duration;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.multipart.MultipartFile;

/** Talks to the Python FastAPI inference service. */
@Service
public class MlClient {

    private static final Logger log = LoggerFactory.getLogger(MlClient.class);

    /** Served when the ML service is offline so the Dashboard is never blank. */
    private static final List<Map<String, Object>> FALLBACK_DISEASES = buildFallback();

    private final RestTemplate restTemplate;
    private final String baseUrl;

    public MlClient(
            RestTemplateBuilder builder,
            @Value("${mediscan.ml.base-url}") String baseUrl,
            @Value("${mediscan.ml.timeout-seconds}") long timeoutSeconds) {
        this.baseUrl = baseUrl.replaceAll("/+$", "");
        this.restTemplate = builder
                .setConnectTimeout(Duration.ofSeconds(10))
                .setReadTimeout(Duration.ofSeconds(timeoutSeconds))
                .build();
    }

    public String getBaseUrl() {
        return baseUrl;
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> listDiseases() {
        try {
            Map<String, Object> result = restTemplate.getForObject(baseUrl + "/diseases", Map.class);
            if (result != null) {
                return result;
            }
        } catch (ResourceAccessException ex) {
            log.warn("ML inference service unreachable at {}. Returning static disease catalogue. Start with: uvicorn app:app --port 8001", baseUrl);
        }
        Map<String, Object> fallback = new LinkedHashMap<>();
        fallback.put("diseases", FALLBACK_DISEASES);
        fallback.put("source", "static_fallback");
        return fallback;
    }

    private static List<Map<String, Object>> buildFallback() {
        return Arrays.asList(
            disease("brain_tumor", "Brain Tumor", "MRI",
                Arrays.asList("Glioma", "Meningioma", "No Tumor", "Pituitary"),
                "pytorch", "resnet18", "TRAINED",
                "Local PyTorch ResNet-18 model for brain tumor classification."),
            disease("knee_osteoarthritis", "Knee Osteoarthritis", "Knee X-ray",
                Arrays.asList("Normal", "Non Severe OA", "Severe OA"),
                "pytorch", "knee_resnet18_1ch", "TRAINED",
                "Model Version3.pth: 3-way severity estimation on knee X-rays."),
            disease("skin_cancer", "Skin Cancer", "Dermoscopy",
                Arrays.asList("Basal Cell Carcinoma (Cancer)", "Melanoma (Cancer)", "Nevus (Non-Cancerous)"),
                "keras", "mobilenetv2", "TRAINED",
                "MobileNetV2 checkpoint trained on dermoscopy skin lesion images."),
            disease("diabetic_retinopathy", "Diabetic Retinopathy", "Retinal Fundus",
                Arrays.asList("No DR", "Mild Non-Proliferative DR", "Moderate Non-Proliferative DR",
                        "Severe Non-Proliferative DR", "Proliferative DR"),
                "keras", "densenet121", "TRAINED",
                "DenseNet121 ordinal classifier for diabetic retinopathy grading."),
            disease("pneumonia", "Pneumonia", "Chest X-ray",
                Arrays.asList("Normal", "Pneumonia"),
                "keras", "densenet121", "TRAINED",
                "DenseNet-121 CheXNet architecture for radiologist-level pneumonia screening.")
        );
    }

    private static Map<String, Object> disease(
            String key, String displayName, String modality,
            List<String> classes, String framework, String architecture,
            String modelStatus, String provenance) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("key", key);
        m.put("display_name", displayName);
        m.put("modality", modality);
        m.put("classes", classes);
        m.put("framework", framework);
        m.put("architecture", architecture);
        m.put("model_status", modelStatus);
        m.put("confidence_threshold", 0.75);
        m.put("provides_stage", false);
        m.put("provenance", provenance);
        m.put("metrics", null);
        return m;
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> health() {
        try {
            return restTemplate.getForObject(baseUrl + "/health", Map.class);
        } catch (ResourceAccessException ex) {
            throw new MlServiceException("ML inference service is unreachable at " + baseUrl);
        }
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> predict(
            String disease,
            String patientName,
            Integer patientAge,
            String patientNotes,
            MultipartFile file) {

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);

        MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
        body.add("disease", disease);
        body.add("patientName", patientName);
        body.add("patientAge", patientAge);
        if (patientNotes != null && !patientNotes.isBlank()) {
            body.add("patientNotes", patientNotes);
        }

        try {
            body.add("file", new ByteArrayResource(file.getBytes()) {
                @Override
                public String getFilename() {
                    String original = file.getOriginalFilename();
                    return original == null || original.isBlank() ? "scan.png" : original;
                }
            });
        } catch (Exception ex) {
            throw new MlServiceException("Could not read the uploaded file.");
        }

        try {
            ResponseEntity<Map> response = restTemplate.postForEntity(
                    baseUrl + "/predict", new HttpEntity<>(body, headers), Map.class);
            return response.getBody();
        } catch (RestClientResponseException ex) {
            // Surface the inference service's own validation message.
            String detail = ex.getResponseBodyAsString();
            log.warn("ML service rejected request: {} {}", ex.getStatusCode(), detail);
            throw new MlServiceException(
                    "Inference rejected: " + shorten(detail), ex.getStatusCode().value());
        } catch (ResourceAccessException ex) {
            throw new MlServiceException(
                    "ML inference service is unreachable at " + baseUrl
                            + ". Start it with: uvicorn app:app --port 8001");
        }
    }

    public byte[] fetchBinary(String path) {
        try {
            HttpHeaders headers = new HttpHeaders();
            headers.setAccept(List.of(MediaType.ALL));
            ResponseEntity<byte[]> response = restTemplate.exchange(
                    baseUrl + path, org.springframework.http.HttpMethod.GET,
                    new HttpEntity<>(headers), byte[].class);
            return response.getBody();
        } catch (RestClientResponseException ex) {
            throw new MlServiceException("Artifact not found: " + path, 404);
        } catch (ResourceAccessException ex) {
            throw new MlServiceException("ML inference service is unreachable.");
        }
    }

    private static String shorten(String value) {
        if (value == null) {
            return "unknown error";
        }
        return value.length() > 300 ? value.substring(0, 300) + "..." : value;
    }

    /** Signals an upstream ML failure, mapped to an HTTP status by the controller advice. */
    public static class MlServiceException extends RuntimeException {
        private final int status;

        public MlServiceException(String message) {
            this(message, 503);
        }

        public MlServiceException(String message, int status) {
            super(message);
            this.status = status;
        }

        public int getStatus() {
            return status;
        }
    }
}
