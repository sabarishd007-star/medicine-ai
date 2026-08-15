package com.mediscan.backend.service;

import com.google.firebase.auth.FirebaseToken;
import com.mediscan.backend.dto.AuthDtos.AuthResponse;
import com.mediscan.backend.dto.AuthDtos.LoginRequest;
import com.mediscan.backend.dto.AuthDtos.ProfileResponse;
import com.mediscan.backend.dto.AuthDtos.RegisterRequest;
import com.mediscan.backend.model.User;
import com.mediscan.backend.repository.ScanRepository;
import com.mediscan.backend.repository.UserRepository;
import com.mediscan.backend.security.FirebaseService;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

@Service
public class AuthService {

    private final UserRepository users;
    private final ScanRepository scans;
    private final FirebaseService firebase;
    private final EmailService emails;

    public AuthService(
            UserRepository users,
            ScanRepository scans,
            FirebaseService firebase,
            EmailService emails) {
        this.users = users;
        this.scans = scans;
        this.firebase = firebase;
        this.emails = emails;
    }

    public AuthResponse register(RegisterRequest request) {
        FirebaseToken token = verifyToken(request.idToken());
        String email = token.getEmail();
        if (email == null) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST, "The Firebase account has no email address.");
        }
        if (users.existsByEmailIgnoreCase(email)) {
            throw new ResponseStatusException(
                    HttpStatus.CONFLICT, "An account with that email already exists.");
        }
        String fullName = request.fullName().trim();
        User user = new User(email, "firebase", fullName);
        users.save(user);
        emails.sendWelcome(email, fullName);
        return buildResponse(user, request.idToken());
    }

    public AuthResponse login(LoginRequest request) {
        FirebaseToken token = verifyToken(request.idToken());
        String email = token.getEmail();
        if (email == null) {
            throw new ResponseStatusException(
                    HttpStatus.UNAUTHORIZED, "The Firebase account has no email address.");
        }
        // A user who signed in through Firebase but never completed our registration
        // still gets a local account so their scans can be tied to them.
        User user = users.findByEmailIgnoreCase(email).orElseGet(() -> {
            String name = token.getName() == null ? email : token.getName();
            return users.save(new User(email, "firebase", name));
        });
        emails.sendLoginNotification(email, user.getFullName());
        return buildResponse(user, request.idToken());
    }

    public User requireUser(String email) {
        if (email == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Authentication required.");
        }
        return users.findByEmailIgnoreCase(email).orElseThrow(() ->
                new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Account no longer exists."));
    }

    public ProfileResponse profile(User user) {
        return new ProfileResponse(
                user.getId(),
                user.getEmail(),
                user.getFullName(),
                user.getRole(),
                scans.countByUser(user));
    }

    private FirebaseToken verifyToken(String idToken) {
        if (idToken == null || idToken.isBlank()) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Missing authentication token.");
        }
        if (!firebase.isConfigured()) {
            throw new ResponseStatusException(
                    HttpStatus.SERVICE_UNAVAILABLE,
                    "Firebase authentication is not configured on the server.");
        }
        try {
            return firebase.verify(idToken);
        } catch (Exception ex) {
            throw new ResponseStatusException(
                    HttpStatus.UNAUTHORIZED, "Invalid or expired authentication token.");
        }
    }

    private AuthResponse buildResponse(User user, String idToken) {
        // Firebase ID tokens live for one hour by default.
        return new AuthResponse(idToken, 60, profile(user));
    }
}
