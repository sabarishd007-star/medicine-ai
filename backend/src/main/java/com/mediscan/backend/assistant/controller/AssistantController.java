package com.mediscan.backend.assistant.controller;

import com.mediscan.backend.assistant.dto.ChatDtos.ChatRequest;
import com.mediscan.backend.assistant.dto.ChatDtos.ChatResponse;
import com.mediscan.backend.assistant.service.AssistantService;
import jakarta.validation.Valid;
import java.util.Map;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Chat endpoint for the general health assistant.
 *
 * <p>React posts here instead of calling the LLM directly, which keeps the API
 * key server-side. The response never echoes provider details or the key.
 */
@RestController
@RequestMapping("/api/assistant")
public class AssistantController {

    private final AssistantService assistant;

    public AssistantController(AssistantService assistant) {
        this.assistant = assistant;
    }

    @PostMapping("/chat")
    public ResponseEntity<ChatResponse> chat(@Valid @RequestBody ChatRequest request) {
        return ResponseEntity.ok(assistant.chat(request));
    }

    /** Lets the UI warn up front if the key is missing, rather than on first send. */
    @GetMapping("/status")
    public ResponseEntity<Map<String, Object>> status() {
        return ResponseEntity.ok(Map.of(
                "configured", assistant.isConfigured(),
                "provider", assistant.getProvider(),
                "disclaimer", AssistantService.DISCLAIMER,
                "scope", "General health information only. Not a diagnostic tool."));
    }
}
