package com.mediscan.backend.service;

import com.mediscan.backend.dto.AuthDtos.AuthResponse;
import com.mediscan.backend.dto.AuthDtos.LoginRequest;
import com.mediscan.backend.dto.AuthDtos.ProfileResponse;
import com.mediscan.backend.dto.AuthDtos.RegisterRequest;
import com.mediscan.backend.model.User;
import com.mediscan.backend.repository.ScanRepository;
import com.mediscan.backend.repository.UserRepository;
import com.mediscan.backend.security.JwtService;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

@Service
public class AuthService {

    private final UserRepository users;
    private final ScanRepository scans;
    private final PasswordEncoder encoder;
    private final JwtService jwt;

    public AuthService(
            UserRepository users,
            ScanRepository scans,
            PasswordEncoder encoder,
            JwtService jwt) {
        this.users = users;
        this.scans = scans;
        this.encoder = encoder;
        this.jwt = jwt;
    }

    public AuthResponse register(RegisterRequest request) {
        String email = request.email().trim().toLowerCase();
        if (users.existsByEmailIgnoreCase(email)) {
            throw new ResponseStatusException(
                    HttpStatus.CONFLICT, "An account with that email already exists.");
        }
        User user = new User(email, encoder.encode(request.password()), request.fullName().trim());
        users.save(user);
        return buildResponse(user);
    }

    public AuthResponse login(LoginRequest request) {
        String email = request.email().trim().toLowerCase();
        User user = users.findByEmailIgnoreCase(email).orElseThrow(() ->
                new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Invalid email or password."));

        if (!encoder.matches(request.password(), user.getPasswordHash())) {
            // Same message as the not-found case: do not reveal which accounts exist.
            throw new ResponseStatusException(
                    HttpStatus.UNAUTHORIZED, "Invalid email or password.");
        }
        return buildResponse(user);
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

    private AuthResponse buildResponse(User user) {
        return new AuthResponse(
                jwt.generate(user.getEmail()), jwt.getExpiryMinutes(), profile(user));
    }
}
