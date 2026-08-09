package com.mediscan.backend.assistant.service;

import java.util.List;
import java.util.Locale;
import java.util.regex.Pattern;

/**
 * Deterministic red-flag detector for the medical assistant.
 *
 * <p>The system prompt already instructs the model to escalate emergencies, but
 * a prompt is a request, not a guarantee: it can be overridden by jailbreaks,
 * degraded by model updates, or skipped entirely if the LLM call fails. This
 * class runs <em>before</em> the model is ever contacted and short-circuits the
 * whole request, so the emergency path does not depend on the model behaving.
 *
 * <p>It is deliberately biased toward false positives. Telling someone with
 * indigestion to seek urgent care wastes their time; failing to escalate a
 * heart attack does not.
 */
public final class EmergencyTriage {

    private EmergencyTriage() {
    }

    /** Self-harm gets its own response with crisis lines rather than "go to A&E". */
    private static final List<Pattern> SELF_HARM = compile(
            "kill myself", "killing myself", "end my life", "ending my life",
            "want to die", "wanna die", "suicidal", "suicide", "take my own life",
            "self harm", "self-harm", "hurt myself", "cutting myself",
            "no reason to live", "better off dead", "overdose on purpose");

    /**
     * Phrases that indicate the user is asking about a condition in the
     * abstract rather than reporting it. "Reading about stroke prevention" is a
     * general question; "I'm having a stroke" is not.
     *
     * <p>This only suppresses single-keyword matches. An explicit first-person
     * report still escalates, because the cost of being wrong is asymmetric.
     */
    private static final List<Pattern> EDUCATIONAL_CONTEXT = compile(
            "reading about", "what is the difference", "in general terms",
            "prevention and", "how do i prevent", "learning about",
            "what does it mean when", "for a school", "for my studies");

    private static final List<Pattern> FIRST_PERSON_URGENT = compile(
            "i am having", "i'm having", "im having", "he is having", "she is having",
            "having a", "i think i'm", "i think i am", "right now", "help me");

    private static final List<Pattern> MEDICAL_EMERGENCY = compile(
            // cardiac / respiratory
            "chest pain", "chest pressure", "chest tightness", "crushing pain",
            "pain in my chest", "heart attack", "cardiac arrest",
            "can't breathe", "cannot breathe", "cant breathe", "not breathing",
            "difficulty breathing", "trouble breathing", "struggling to breathe",
            "shortness of breath", "gasping", "choking", "turning blue",
            // neurological
            "unconscious", "unresponsive", "passed out", "fainted and won't wake",
            "loss of consciousness", "lost consciousness", "won't wake up",
            "seizure", "convulsing", "convulsion", "fitting",
            "stroke", "face drooping", "slurred speech", "sudden numbness",
            "worst headache of my life", "thunderclap headache",
            // haemorrhage / trauma
            "severe bleeding", "heavy bleeding", "bleeding heavily",
            "won't stop bleeding", "wont stop bleeding", "blood spurting",
            "coughing up blood", "vomiting blood", "hemorrhage", "haemorrhage",
            "deep wound", "stabbed", "gunshot", "severe burn",
            // other time-critical
            "anaphylaxis", "anaphylactic", "throat closing", "tongue swelling",
            "overdose", "poisoned", "swallowed poison", "drowning",
            "stiff neck and fever", "blood in stool and dizzy",
            // Reversed / passive phrasings the forward patterns above miss.
            "throat closing up", "closing up", "bleeding is severe",
            "bleeding heavily", "bleeding badly", "losing a lot of blood");

    /**
     * Builds a matcher for each phrase that tolerates small filler words between
     * the terms, so "throat is closing" and "throat closing" both match. Without
     * this the guard misses ordinary phrasing - a real anaphylaxis description
     * slipped through in testing for exactly that reason.
     */
    private static List<Pattern> compile(String... phrases) {
        return java.util.Arrays.stream(phrases)
                .map(phrase -> {
                    String regex = java.util.Arrays.stream(phrase.split(" "))
                            .map(Pattern::quote)
                            // allow up to two short filler words (is, my, the, feels...)
                            .reduce((a, b) -> a + "(?:\\W+\\w+){0,2}\\W+" + b)
                            .orElse(Pattern.quote(phrase));
                    return Pattern.compile(regex, Pattern.CASE_INSENSITIVE);
                })
                .toList();
    }

    public enum Level {
        NONE,
        MEDICAL_EMERGENCY,
        SELF_HARM
    }

    public static Level assess(String message) {
        if (message == null || message.isBlank()) {
            return Level.NONE;
        }
        String text = message.toLowerCase(Locale.ROOT);

        // Self-harm is checked first: it needs crisis support, not an ambulance.
        // It is never suppressed by educational context - "reading about
        // suicide" still warrants offering support.
        if (SELF_HARM.stream().anyMatch(p -> p.matcher(text).find())) {
            return Level.SELF_HARM;
        }

        if (MEDICAL_EMERGENCY.stream().anyMatch(p -> p.matcher(text).find())) {
            boolean educational = EDUCATIONAL_CONTEXT.stream().anyMatch(p -> p.matcher(text).find());
            boolean firstPerson = FIRST_PERSON_URGENT.stream().anyMatch(p -> p.matcher(text).find());

            // Suppress only when the phrasing is clearly academic AND the user
            // is not describing something happening to them right now.
            if (educational && !firstPerson) {
                return Level.NONE;
            }
            return Level.MEDICAL_EMERGENCY;
        }
        return Level.NONE;
    }

    public static String responseFor(Level level) {
        return switch (level) {
            case MEDICAL_EMERGENCY -> """
                    **This may be a medical emergency. Please seek help now.**

                    Call your local emergency number immediately:
                    - India: **108** (ambulance) or **112** (all emergencies)
                    - UK/EU: **999** / **112**
                    - US/Canada: **911**

                    If someone is with you, ask them to help you get to the nearest \
                    emergency department. Do not drive yourself if you feel faint, \
                    breathless, or have chest pain.

                    I am not able to assess symptoms like these, and waiting for \
                    information online can cost time that matters. Please contact \
                    emergency services now.""";

            case SELF_HARM -> """
                    **I'm concerned about what you've described, and I want you to \
                    get proper support.**

                    Please reach out to someone who can help right now:
                    - India: **AASRA 9820466726**, or **Tele-MANAS 14416** (24x7)
                    - UK: **Samaritans 116 123**
                    - US: **988** Suicide & Crisis Lifeline
                    - Or call your local emergency number if you are in immediate danger.

                    If you can, tell someone you trust how you're feeling, or go to \
                    your nearest emergency department. You deserve support from a \
                    real person, and I'm not a substitute for that.

                    I'm not able to help with other questions while you're feeling \
                    this way - please contact one of the services above.""";

            case NONE -> "";
        };
    }
}
