package com.mediscan.backend.assistant.service;

import com.mediscan.backend.assistant.dto.ChatDtos.ChatMessage;
import com.mediscan.backend.assistant.dto.ChatDtos.ChatRequest;
import com.mediscan.backend.assistant.dto.ChatDtos.ChatResponse;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

/**
 * Server-side bridge to the LLM for the general health assistant.
 *
 * <p>The API key never leaves the backend. React talks only to this service, so
 * the key is not present in any bundle a user can read.
 */
@Service
public class AssistantService {

    private static final Logger log = LoggerFactory.getLogger(AssistantService.class);

    public static final String DISCLAIMER =
            "This is general health information, not a diagnosis. "
                    + "It is not a replacement for professional medical advice.";

    /**
     * Rules the model must follow. These are duplicated by real code paths where
     * it matters: emergencies are caught by {@link EmergencyTriage} before the
     * model is called, because a prompt alone is not a safety control.
     */
    static final String SYSTEM_PROMPT = """
            You are the Medical Assistant inside MediScan AI, a clinical decision \
            support platform. You provide general, educational health information \
            to members of the public.

            You are NOT a diagnostic tool. MediScan AI's image-based CNN modules are \
            a separate feature; you do not analyse images, scans or lab results, and \
            you must not imply that you do.

            Follow every one of these rules in every response:

            1. NEVER give a definitive diagnosis. Do not say "you have X". Use \
               language such as "this can sometimes be associated with" or \
               "common causes include".

            2. ALWAYS mention two or three plausible common causes rather than a \
               single one. Naming only one cause implies a certainty you do not \
               have.

            3. ALWAYS end with a clear line recommending the reader consult a \
               qualified healthcare professional, especially if symptoms persist, \
               worsen, or are severe.

            4. If the user describes anything potentially life-threatening - chest \
               pain, difficulty breathing, severe bleeding, loss of consciousness, \
               stroke signs, anaphylaxis, poisoning, or thoughts of self-harm or \
               suicide - respond ONLY by directing them to emergency services or a \
               crisis line. Do not discuss the symptom, do not list causes, and do \
               not offer any other information in that reply.

            5. NEVER recommend specific medications by brand or generic name, and \
               never give dosages, frequencies, or prescription advice. You may \
               refer in general terms to "over-the-counter pain relief" and tell \
               the user to follow the package instructions or ask a pharmacist.

            6. Do not speculate about rare or frightening conditions unless the user \
               raises them. If asked directly, answer factually and calmly.

            7. If a question is outside general health information - legal advice, \
               a request to interpret a specific scan, or anything unrelated to \
               health - say plainly that it is outside what you can help with.

            Style: plain language, warm but not casual, no emoji. Keep replies under \
            roughly 200 words. Use short paragraphs or bullets. Never invent \
            statistics or cite studies you cannot verify.
            """;

    private final RestTemplate restTemplate;
    private final String provider;
    private final String apiKey;
    private final String model;
    private final String openAiUrl;
    private final String anthropicUrl;
    private final int maxTokens;
    private final int maxHistory;

    public AssistantService(
            RestTemplateBuilder builder,
            @Value("${mediscan.assistant.provider:openai}") String provider,
            @Value("${mediscan.assistant.api-key:}") String apiKey,
            @Value("${mediscan.assistant.model:gpt-4o-mini}") String model,
            @Value("${mediscan.assistant.openai-url:https://api.openai.com/v1/chat/completions}")
                    String openAiUrl,
            @Value("${mediscan.assistant.anthropic-url:https://api.anthropic.com/v1/messages}")
                    String anthropicUrl,
            @Value("${mediscan.assistant.max-tokens:600}") int maxTokens,
            @Value("${mediscan.assistant.max-history:10}") int maxHistory,
            @Value("${mediscan.assistant.timeout-seconds:45}") long timeoutSeconds) {

        this.provider = provider == null ? "openai" : provider.trim().toLowerCase();
        this.apiKey = apiKey == null ? "" : apiKey.trim();
        this.model = model;
        this.openAiUrl = openAiUrl;
        this.anthropicUrl = anthropicUrl;
        this.maxTokens = maxTokens;
        this.maxHistory = maxHistory;
        this.restTemplate = builder
                .setConnectTimeout(Duration.ofSeconds(10))
                .setReadTimeout(Duration.ofSeconds(timeoutSeconds))
                .build();
    }

    public boolean isConfigured() {
        return !apiKey.isBlank();
    }

    public String getProvider() {
        return provider;
    }

    public ChatResponse chat(ChatRequest request) {
        // Safety first: this runs before any network call, so an emergency is
        // handled even if the model is misconfigured, jailbroken or offline.
        EmergencyTriage.Level level = EmergencyTriage.assess(request.message());
        if (level != EmergencyTriage.Level.NONE) {
            log.info("Assistant: emergency guard triggered ({})", level);
            return new ChatResponse(
                    EmergencyTriage.responseFor(level),
                    true,
                    "safety_guard",
                    false,
                    DISCLAIMER,
                    Instant.now());
        }

        if (!isConfigured()) {
            return new ChatResponse(
                    """
                    The medical assistant is not configured on this server yet.

                    An administrator needs to set the MEDISCAN_ASSISTANT_API_KEY \
                    environment variable. Until then I cannot answer health \
                    questions. For anything urgent, contact a healthcare \
                    professional or your local emergency number.""",
                    false,
                    "not_configured",
                    true,
                    DISCLAIMER,
                    Instant.now());
        }

        try {
            String reply = "anthropic".equals(provider)
                    ? callAnthropic(request)
                    : callOpenAi(request);

            if (reply == null || reply.isBlank()) {
                return unavailable("The assistant returned an empty response.");
            }
            return new ChatResponse(reply.trim(), false, "llm", false, DISCLAIMER, Instant.now());

        } catch (Exception ex) {
            // Never surface provider internals or the key to the client.
            log.warn("Assistant: LLM call failed: {}", ex.getMessage());
            return unavailable("The assistant could not be reached just now.");
        }
    }

    private ChatResponse unavailable(String reason) {
        return new ChatResponse(
                reason
                        + """
                        \n\nPlease try again in a moment. If your question is urgent, \
                        contact a healthcare professional or your local emergency \
                        number rather than waiting.""",
                false,
                "unavailable",
                true,
                DISCLAIMER,
                Instant.now());
    }

    /** Trims history so a long session cannot blow the context window or the bill. */
    private List<ChatMessage> boundedHistory(ChatRequest request) {
        List<ChatMessage> history = request.history() == null ? List.of() : request.history();
        List<ChatMessage> cleaned = new ArrayList<>();
        for (ChatMessage message : history) {
            if (message == null || message.content() == null || message.content().isBlank()) {
                continue;
            }
            String role = "assistant".equalsIgnoreCase(message.role()) ? "assistant" : "user";
            cleaned.add(new ChatMessage(role, message.content()));
        }
        int from = Math.max(0, cleaned.size() - maxHistory);
        return cleaned.subList(from, cleaned.size());
    }

    @SuppressWarnings("unchecked")
    private String callOpenAi(ChatRequest request) {
        List<Map<String, String>> messages = new ArrayList<>();
        messages.add(Map.of("role", "system", "content", SYSTEM_PROMPT));
        for (ChatMessage message : boundedHistory(request)) {
            messages.add(Map.of("role", message.role(), "content", message.content()));
        }
        messages.add(Map.of("role", "user", "content", request.message()));

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("model", model);
        body.put("messages", messages);
        body.put("max_tokens", maxTokens);
        body.put("temperature", 0.3);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.setBearerAuth(apiKey);

        Map<String, Object> response =
                restTemplate.postForObject(openAiUrl, new HttpEntity<>(body, headers), Map.class);
        if (response == null) {
            return null;
        }
        List<Map<String, Object>> choices = (List<Map<String, Object>>) response.get("choices");
        if (choices == null || choices.isEmpty()) {
            return null;
        }
        Map<String, Object> message = (Map<String, Object>) choices.get(0).get("message");
        return message == null ? null : (String) message.get("content");
    }

    @SuppressWarnings("unchecked")
    private String callAnthropic(ChatRequest request) {
        List<Map<String, String>> messages = new ArrayList<>();
        for (ChatMessage message : boundedHistory(request)) {
            messages.add(Map.of("role", message.role(), "content", message.content()));
        }
        messages.add(Map.of("role", "user", "content", request.message()));

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("model", model);
        // Anthropic takes the system prompt as a top-level field, not a message.
        body.put("system", SYSTEM_PROMPT);
        body.put("messages", messages);
        body.put("max_tokens", maxTokens);
        body.put("temperature", 0.3);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("x-api-key", apiKey);
        headers.set("anthropic-version", "2023-06-01");

        Map<String, Object> response =
                restTemplate.postForObject(anthropicUrl, new HttpEntity<>(body, headers), Map.class);
        if (response == null) {
            return null;
        }
        List<Map<String, Object>> content = (List<Map<String, Object>>) response.get("content");
        if (content == null || content.isEmpty()) {
            return null;
        }
        return (String) content.get(0).get("text");
    }
}
