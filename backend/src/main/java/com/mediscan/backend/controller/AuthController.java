package com.mediscan.backend.controller;

import com.mediscan.backend.dto.AuthDtos.AuthResponse;
import com.mediscan.backend.dto.AuthDtos.LoginRequest;
import com.mediscan.backend.dto.AuthDtos.ProfileResponse;
import com.mediscan.backend.dto.AuthDtos.RegisterRequest;
import com.mediscan.backend.service.AuthService;
import jakarta.validation.Valid;
import java.security.Principal;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private final AuthService auth;

    public AuthController(AuthService auth) {
        this.auth = auth;
    }

    @PostMapping("/register")
    public ResponseEntity<AuthResponse> register(@Valid @RequestBody RegisterRequest request) {
        return ResponseEntity.ok(auth.register(request));
    }

    @PostMapping("/login")
    public ResponseEntity<AuthResponse> login(@Valid @RequestBody LoginRequest request) {
        return ResponseEntity.ok(auth.login(request));
    }

    @GetMapping("/me")
    public ResponseEntity<ProfileResponse> me(Principal principal) {
        var user = auth.requireUser(principal == null ? null : principal.getName());
        return ResponseEntity.ok(auth.profile(user));
    }
}
