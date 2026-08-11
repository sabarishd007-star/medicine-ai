package com.mediscan.backend.assistant.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.mediscan.backend.assistant.dto.ChatDtos.ChatMessage;
import com.mediscan.backend.assistant.dto.ChatDtos.ChatRequest;
import com.mediscan.backend.assistant.dto.ChatDtos.ChatResponse;
import com.mediscan.backend.assistant.dto.ChatDtos.PossibleCondition;
import com.mediscan.backend.assistant.dto.ChatDtos.SymptomAnalysis;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
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
     *
     * <p>The structured-symptom block makes the assistant return a machine-readable
     * analysis alongside its prose, so the React UI can render possible conditions
     * as discrete cards instead of parsing free text.
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
               language such as "based on what you've described, some possibilities \
               include" or "this can sometimes be associated with".

            2. ALWAYS mention two or three plausible common causes rather than a \
               single one. Naming only one cause implies a certainty you do not have. \
               Prefer common explanations over rare ones.

            3. ALWAYS end with a clear line recommending the reader consult a \
               qualified healthcare professional, especially if symptoms persist, \
               worsen, or are severe.

            4. If the user describes anything potentially life-threatening - chest \
               pain, difficulty breathing, severe bleeding, loss of consciousness, \
               stroke signs, anaphylaxis, or thoughts of self-harm or suicide - \
               respond ONLY by directing them to emergency services or a crisis \
               line. Do not discuss the symptom, do not list causes, and do not \
               offer any other information in that reply.

            5. NEVER recommend specific medications by brand or generic name, and \
               never give dosages, frequencies, or prescription advice. You may \
               refer in general terms to "over-the-counter pain relief" and tell \
               the user to follow the package instructions or ask a pharmacist.

            6. Do not speculate about rare or frightening conditions unless the user \
               raises them. If asked directly, answer factually and calmly.

            7. If a question is outside general health information - legal advice, \
               a request to interpret a specific scan, or anything unrelated to \
               health - say plainly that it is outside what you can help with.

            --- STRUCTURED SYMPTOM ANALYSIS ---
            When the user describes symptoms, ALSO include a JSON block at the end \
            of your reply wrapped in triple backticks with the language tag \
            `analysis`. Use EXACTLY this shape:

            ```json
            {
              "conditions": [
                {
                  "name": "Common condition name (no brand names)",
                  "likelihood": "common",
                  "briefExplanation": "One sentence tying it to the symptoms described"
                }
              ],
              "urgency": "self-care | see-doctor-soon | emergency",
              "recommendedAction": "One sentence on what to do next",
              "summary": "One plain-language sentence framing these as possibilities"
            }
            ```

            Rules for the JSON block:
            - "likelihood" MUST be exactly "common", "possible", or "less common".
            - Include 2-4 conditions, ordered from most to least likely.
            - "urgency": "self-care" for mild/vague symptoms, "see-doctor-soon" for \
              anything persisting beyond a few days or interfering with daily life, \
              "emergency" ONLY for the red-flag cases in rule 4 (those never reach \
              this block because rule 4 fires first).
            - NEVER put a diagnosis in "name" - phrase it as "Possible X" or \
              "X (a condition that...)".
            - The JSON MUST be valid and the only code block in your reply.

            Style: plain language, warm but not casual, no emoji. Keep prose under \
            roughly 200 words. Use short paragraphs or bullets. Never invent \
            statistics or cite studies you cannot verify.
            """;

    private static final Pattern ANALYSIS_BLOCK =
            Pattern.compile("```json\\s*(\\{.*?\\})\\s*```", Pattern.DOTALL);

    private static final ObjectMapper MAPPER = new ObjectMapper();

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
                    Instant.now(),
                    null);
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
                    Instant.now(),
                    null);
        }

        try {
            String reply = "anthropic".equals(provider)
                    ? callAnthropic(request)
                    : callOpenAi(request);

            if (reply == null || reply.isBlank()) {
                return unavailable("The assistant returned an empty response.");
            }

            // Pull the structured analysis out of the reply. The prose keeps the
            // JSON block so the raw text still reads naturally; the parsed form
            // drives the UI cards. If parsing fails we still return the prose.
            String prose = reply.trim();
            SymptomAnalysis analysis = null;
            try {
                analysis = extractAnalysis(prose);
                if (analysis != null) {
                    prose = prose.replaceFirst("```json\\s*\\{.*?\\}\\s*```", "").trim();
                }
            } catch (Exception ex) {
                log.debug("Could not parse analysis block: {}", ex.getMessage());
            }

            return new ChatResponse(
                    prose, false, "llm", false, DISCLAIMER, Instant.now(), analysis);

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
                Instant.now(),
                null);
    }

    /**
     * Extracts the structured symptom analysis from the model's reply. Returns
     * null when there is no analysis block or it fails to parse — the prose is
     * still useful, so this degrades gracefully rather than erroring.
     */
    private SymptomAnalysis extractAnalysis(String reply) throws JsonProcessingException {
        Matcher matcher = ANALYSIS_BLOCK.matcher(reply);
        if (!matcher.find()) {
            return null;
        }
        JsonNode root = MAPPER.readTree(matcher.group(1));

        List<PossibleCondition> conditions = new ArrayList<>();
        JsonNode conditionsNode = root.get("conditions");
        if (conditionsNode != null && conditionsNode.isArray()) {
            for (JsonNode node : conditionsNode) {
                String name = textOr(node, "name", "Possible condition");
                String likelihood = normaliseLikelihood(textOr(node, "likelihood", "possible"));
                String explanation = textOr(node, "briefExplanation", "");
                conditions.add(new PossibleCondition(name, likelihood, explanation));
            }
        }

        if (conditions.isEmpty()) {
            return null;
        }

        return new SymptomAnalysis(
                conditions,
                normaliseUrgency(textOr(root, "urgency", "see-doctor-soon")),
                textOr(root, "recommendedAction", "Consider consulting a healthcare professional."),
                textOr(root, "summary", "Based on what you described, here are some possibilities."));
    }

    private static String normaliseLikelihood(String value) {
        if (value == null) {
            return "possible";
        }
        return switch (value.trim().toLowerCase()) {
            case "common" -> "common";
            case "less common", "less-common", "lesscommon", "rare" -> "less common";
            default -> "possible";
        };
    }

    private static String normaliseUrgency(String value) {
        if (value == null) {
            return "see-doctor-soon";
        }
        return switch (value.trim().toLowerCase()) {
            case "self-care", "self care", "selfcare" -> "self-care";
            case "emergency" -> "emergency";
            default -> "see-doctor-soon";
        };
    }

    private static String textOr(JsonNode node, String field, String fallback) {
        JsonNode value = node.get(field);
        return (value == null || value.isNull() || value.asText().isBlank())
                ? fallback
                : value.asText();
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
