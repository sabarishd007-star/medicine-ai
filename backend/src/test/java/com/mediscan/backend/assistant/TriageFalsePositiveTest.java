package com.mediscan.backend.assistant;

import static org.assertj.core.api.Assertions.assertThat;

import com.mediscan.backend.assistant.service.EmergencyTriage;
import com.mediscan.backend.assistant.service.EmergencyTriage.Level;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

/**
 * The matcher tolerates filler words between phrase terms so that "throat is
 * closing" is caught. That flexibility could over-trigger, so these cases pin
 * down the boundary: escalating every mention of the word "chest" would make
 * the assistant useless.
 */
class TriageFalsePositiveTest {

    @ParameterizedTest
    @ValueSource(strings = {
        "I have a chest infection that started last week",
        "What chest exercises are safe with a bad shoulder?",
        "My chest feels congested from a cold",
        "I get breathless walking up three flights of stairs",
        "reading about stroke prevention and diet",
        "my nose is bleeding slightly in dry weather",
        "I bruise easily, is that normal?",
        "what is the difference between a seizure disorder and epilepsy in general terms",
        "my throat is sore and scratchy"
    })
    @DisplayName("descriptive, non-urgent phrasing is not escalated")
    void doesNotOverTrigger(String message) {
        assertThat(EmergencyTriage.assess(message)).isEqualTo(Level.NONE);
    }

    @ParameterizedTest
    @ValueSource(strings = {
        "my throat is closing after eating peanuts",
        "my throat feels like it is closing up",
        "I have severe bleeding from my leg",
        "the bleeding is severe and won't stop",
        "he is not breathing",
        "my chest has a crushing pain"
    })
    @DisplayName("natural phrasing with filler words still escalates")
    void catchesNaturalPhrasing(String message) {
        assertThat(EmergencyTriage.assess(message)).isEqualTo(Level.MEDICAL_EMERGENCY);
    }
}
