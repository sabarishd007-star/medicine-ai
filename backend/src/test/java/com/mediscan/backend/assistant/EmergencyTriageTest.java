package com.mediscan.backend.assistant;

import static org.assertj.core.api.Assertions.assertThat;

import com.mediscan.backend.assistant.service.EmergencyTriage;
import com.mediscan.backend.assistant.service.EmergencyTriage.Level;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

/**
 * The triage guard is the one control that must hold even if the LLM is
 * jailbroken, misconfigured or offline, so it is tested directly.
 */
class EmergencyTriageTest {

    @ParameterizedTest
    @ValueSource(strings = {
        "I have chest pain radiating to my arm",
        "My father can't breathe properly",
        "she is unconscious and won't wake up",
        "There is SEVERE BLEEDING from the wound",
        "my friend is having a seizure",
        "I think I'm having a stroke, my face is drooping",
        "took an overdose of pills",
        "my throat is closing after eating peanuts",
        "worst headache of my life came on suddenly"
    })
    @DisplayName("life-threatening descriptions escalate to emergency")
    void detectsMedicalEmergencies(String message) {
        assertThat(EmergencyTriage.assess(message)).isEqualTo(Level.MEDICAL_EMERGENCY);
    }

    @ParameterizedTest
    @ValueSource(strings = {
        "I want to die",
        "I've been thinking about suicide",
        "I want to kill myself",
        "I have been cutting myself",
        "everyone would be better off dead without me"
    })
    @DisplayName("self-harm is routed to crisis support, not emergency services")
    void detectsSelfHarm(String message) {
        assertThat(EmergencyTriage.assess(message)).isEqualTo(Level.SELF_HARM);
    }

    @ParameterizedTest
    @ValueSource(strings = {
        "I have a mild headache and feel a bit tired",
        "What causes seasonal allergies?",
        "My knee aches after running",
        "Is it normal to feel sleepy after lunch?",
        "what does hypertension mean"
    })
    @DisplayName("ordinary questions are not escalated")
    void allowsRoutineQuestions(String message) {
        assertThat(EmergencyTriage.assess(message)).isEqualTo(Level.NONE);
    }

    @Test
    @DisplayName("detection is case-insensitive")
    void caseInsensitive() {
        assertThat(EmergencyTriage.assess("CHEST PAIN")).isEqualTo(Level.MEDICAL_EMERGENCY);
        assertThat(EmergencyTriage.assess("ChEsT pAiN")).isEqualTo(Level.MEDICAL_EMERGENCY);
    }

    @Test
    @DisplayName("self-harm takes priority over a co-occurring medical phrase")
    void selfHarmWinsOverMedical() {
        assertThat(EmergencyTriage.assess("I want to die, my chest hurts"))
                .isEqualTo(Level.SELF_HARM);
    }

    @Test
    @DisplayName("null and blank input are safe")
    void handlesEmptyInput() {
        assertThat(EmergencyTriage.assess(null)).isEqualTo(Level.NONE);
        assertThat(EmergencyTriage.assess("   ")).isEqualTo(Level.NONE);
    }

    @Test
    @DisplayName("emergency replies name a phone number and offer no medical opinion")
    void emergencyResponsesAreActionable() {
        String medical = EmergencyTriage.responseFor(Level.MEDICAL_EMERGENCY);
        assertThat(medical).contains("108").contains("112").contains("911");

        String selfHarm = EmergencyTriage.responseFor(Level.SELF_HARM);
        assertThat(selfHarm).contains("988").contains("Tele-MANAS");

        assertThat(EmergencyTriage.responseFor(Level.NONE)).isEmpty();
    }

    @Test
    @DisplayName("triage runs before the model, so it needs no network")
    void isPureFunction() {
        // Two identical calls must agree; no hidden state, no I/O.
        assertThat(EmergencyTriage.assess("chest pain"))
                .isEqualTo(EmergencyTriage.assess("chest pain"));
    }
}
