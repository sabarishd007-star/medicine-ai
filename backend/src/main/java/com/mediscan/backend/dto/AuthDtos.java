package com.mediscan.backend.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public final class AuthDtos {

    private AuthDtos() {
    }

    public record RegisterRequest(
            @NotBlank @Email String email,
            @NotBlank @Size(min = 8, max = 100, message = "Password must be at least 8 characters")
            String password,
            @NotBlank @Size(max = 120) String fullName) {
    }

    public record LoginRequest(
            @NotBlank @Email String email,
            @NotBlank String password) {
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
