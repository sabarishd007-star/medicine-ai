package com.mediscan.backend.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public final class AuthDtos {

    private AuthDtos() {
    }

    public record RegisterRequest(
            @NotBlank String idToken,
            @NotBlank @Size(max = 120) String fullName) {
    }

    public record LoginRequest(
            @NotBlank String idToken) {
    }

    public record AuthResponse(
            String token,
            long expiresInMinutes,
            ProfileResponse user) {
    }

    public record ProfileResponse(
            Long id,
            String email,
            String fullName,
            String role,
            long scanCount) {
    }
}
