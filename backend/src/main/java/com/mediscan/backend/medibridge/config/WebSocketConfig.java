package com.mediscan.backend.medibridge.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.messaging.simp.config.MessageBrokerRegistry;
import org.springframework.web.socket.config.annotation.EnableWebSocketMessageBroker;
import org.springframework.web.socket.config.annotation.StompEndpointRegistry;
import org.springframework.web.socket.config.annotation.WebSocketMessageBrokerConfigurer;

/**
 * STOMP over SockJS for live resource updates.
 *
 * <p>Clients connect to {@code /ws} and subscribe to {@code /topic/resources}.
 * When an admin posts a status change, {@code ResourceService} publishes to
 * that topic and every open client updates without polling.
 *
 * <p>SockJS is enabled so the demo still works if a proxy or network blocks
 * raw WebSocket frames - it falls back to HTTP streaming automatically. The
 * React client also polls on a slow timer as a second safety net, so a broken
 * socket degrades rather than freezing the page.
 */
@Configuration
@EnableWebSocketMessageBroker
public class WebSocketConfig implements WebSocketMessageBrokerConfigurer {

    private final String allowedOrigins;

    public WebSocketConfig(@Value("${mediscan.cors.allowed-origins}") String allowedOrigins) {
        this.allowedOrigins = allowedOrigins;
    }

    @Override
    public void configureMessageBroker(MessageBrokerRegistry registry) {
        // In-memory broker: adequate for a single-instance deployment. Scaling
        // to multiple instances would need an external relay so that an update
        // handled by one node reaches clients connected to another.
        registry.enableSimpleBroker("/topic");
        registry.setApplicationDestinationPrefixes("/app");
    }

    @Override
    public void registerStompEndpoints(StompEndpointRegistry registry) {
        registry.addEndpoint("/ws")
                .setAllowedOriginPatterns(allowedOrigins.split(","))
                .withSockJS();
    }
}
