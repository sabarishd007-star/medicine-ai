package com.mediscan.backend.security;

import com.google.auth.oauth2.GoogleCredentials;
import com.google.firebase.FirebaseApp;
import com.google.firebase.FirebaseOptions;
import com.google.firebase.auth.FirebaseAuth;
import com.google.firebase.auth.FirebaseToken;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Objects;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

/**
 * Wraps the Firebase Admin SDK. Reads the service-account JSON from disk and
 * verifies Firebase ID tokens issued to the browser client.
 */
@Service
public class FirebaseService {

    private static final Logger log = LoggerFactory.getLogger(FirebaseService.class);

    private final FirebaseAuth auth;

    public FirebaseService(@Value("${mediscan.firebase.service-account-path:}") String path) {
        FirebaseApp app = initializeApp(path);
        this.auth = app == null ? null : FirebaseAuth.getInstance(app);
    }

    public boolean isConfigured() {
        return auth != null;
    }

    /**
     * Verifies a Firebase ID token and returns the verified token claims.
     *
     * @throws com.google.firebase.auth.FirebaseAuthException when the token is invalid/expired
     * @throws IllegalStateException when Firebase is not configured
     */
    public FirebaseToken verify(String idToken) throws com.google.firebase.auth.FirebaseAuthException {
        if (auth == null) {
            throw new IllegalStateException("Firebase is not configured.");
        }
        return auth.verifyIdToken(idToken);
    }

    private FirebaseApp initializeApp(String serviceAccountPath) {
        if (serviceAccountPath == null || serviceAccountPath.isBlank()) {
            log.warn("mediscan.firebase.service-account-path is not set; Firebase auth is disabled.");
            return null;
        }
        Path file = Path.of(serviceAccountPath);
        if (!Files.exists(file)) {
            log.warn("Firebase service-account file not found: {}", serviceAccountPath);
            return null;
        }
        try (InputStream in = Files.newInputStream(file)) {
            FirebaseOptions options = FirebaseOptions.builder()
                    .setCredentials(GoogleCredentials.fromStream(in))
                    .build();
            return FirebaseApp.initializeApp(options);
        } catch (IOException ex) {
            throw new IllegalStateException("Could not load Firebase service account from " + serviceAccountPath, ex);
        }
    }
}
