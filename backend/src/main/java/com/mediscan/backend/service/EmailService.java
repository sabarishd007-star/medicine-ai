package com.mediscan.backend.service;

import java.time.Instant;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.stereotype.Service;

@Service
public class EmailService {

    private static final Logger log = LoggerFactory.getLogger(EmailService.class);

    private final JavaMailSender mailSender;
    private final String from;

    public EmailService(
            JavaMailSender mailSender,
            @Value("${spring.mail.username:}") String from) {
        this.mailSender = mailSender;
        this.from = from.isBlank() ? "MediScan AI <no-reply@mediscan.local>" : from;
    }

    public void sendWelcome(String to, String fullName) {
        send(to, "Welcome to MediScan AI",
                "Hi " + firstName(fullName) + ",\n\n"
                        + "Your MediScan AI account is ready. You can now upload scans, "
                        + "get AI-powered screening results, and keep a history of your reports.\n\n"
                        + "Stay healthy!\nThe MediScan AI team");
    }

    public void sendLoginNotification(String to, String fullName) {
        send(to, "New sign-in to your MediScan AI account",
                "Hi " + firstName(fullName) + ",\n\n"
                        + "We noticed a successful sign-in to your MediScan AI account at "
                        + Instant.now() + ".\n\n"
                        + "If this was you, no action is needed. If you don't recognise this "
                        + "sign-in, please reset your password immediately.\n\n"
                        + "The MediScan AI team");
    }

    private void send(String to, String subject, String body) {
        try {
            SimpleMailMessage message = new SimpleMailMessage();
            message.setFrom(from);
            message.setTo(to);
            message.setSubject(subject);
            message.setText(body);
            mailSender.send(message);
            log.info("Email sent to {}", to);
        } catch (Exception ex) {
            // A login must never fail because a notification email could not be sent.
            log.warn("Could not send '{}' to {}: {}", subject, to, ex.getMessage());
        }
    }

    private String firstName(String fullName) {
        if (fullName == null || fullName.isBlank()) {
            return "there";
        }
        return fullName.trim().split("\\s+")[0];
    }
}
