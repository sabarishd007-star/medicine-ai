package com.mediscan.backend.controller;

import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/api/scans")
@CrossOrigin(origins = "*")
public class ScanController {

    @PostMapping("/analyze")
    public ResponseEntity<?> analyzeScan(
            @RequestParam("disease") String disease,
            @RequestParam("patientName") String patientName,
            @RequestParam("patientAge") Integer patientAge,
            @RequestParam("file") MultipartFile file) throws Exception {

        RestTemplate restTemplate = new RestTemplate();
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);

        MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
        body.add("disease", disease);
        body.add("patientName", patientName);
        body.add("patientAge", patientAge);
        body.add("file", new ByteArrayResource(file.getBytes()) {
            @Override
            public String getFilename() {
                return file.getOriginalFilename();
            }
        });

        HttpEntity<MultiValueMap<String, Object>> requestEntity = new HttpEntity<>(body, headers);

        // Forward to Python FastAPI server running on port 8001
        ResponseEntity<String> response = restTemplate.postForEntity(
                "http://localhost:8001/predict",
                requestEntity,
                String.class
        );

        return ResponseEntity.ok(response.getBody());
    }
}