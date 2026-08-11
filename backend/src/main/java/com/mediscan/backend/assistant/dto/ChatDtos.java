package com.mediscan.backend.assistant.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.time.Instant;
import java.util.List;

public final class ChatDtos {

    private ChatDtos() {
    }

    /** One turn of the conversation. {@code role} is "user" or "assistant". */
    public record ChatMessage(String role, String content) {
    }

    public record ChatRequest(
            @NotBlank(message = "Message cannot be empty")
            @Size(max = 4000, message = "Message is too long (max 4000 characters)")
            String message,
            List<ChatMessage> history) {
    }

    /**
     * @param emergency        true when the safety guard escalated, so the UI can
     *                         render the reply as an alert rather than normal chat
     * @param source           "safety_guard" or "llm" - makes it visible that some
     *                         replies never reached the model
     * @param modelUnavailable true when the LLM could not be reached, so the client
     *                         does not present a fallback string as a real answer
     */
    public record ChatResponse(
            String reply,
            boolean emergency,
            String source,
            boolean modelUnavailable,
            String disclaimer,
            Instant at,
            SymptomAnalysis analysis) {
    }

    /**
     * Structured symptom analysis. {@code conditions} are possibilities, not a
     * diagnosis — the UI must render them with that framing. Null when the
     * request was not a symptom analysis (general question or emergency).
     */
    public record SymptomAnalysis(
            java.util.List<PossibleCondition> conditions,
            String urgency,
            String recommendedAction,
            String summary) {
    }

    public record PossibleCondition(
            String name,
            String likelihood, // "common", "possible", "less common"
            String briefExplanation) {
    }
}
