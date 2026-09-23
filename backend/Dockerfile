FROM eclipse-temurin:17-jdk-alpine AS builder
WORKDIR /app

COPY gradlew build.gradle settings.gradle gradle.properties ./
COPY gradle ./gradle
COPY src ./src

RUN chmod +x gradlew && ./gradlew bootJar --no-daemon -x test

FROM eclipse-temurin:17-jre-alpine
WORKDIR /app

RUN addgroup -S mediscan && adduser -S mediscan -G mediscan
COPY --from=builder --chown=mediscan:mediscan /app/build/libs/*.jar app.jar
USER mediscan

EXPOSE 8080
ENTRYPOINT ["java", "-Djava.security.egd=file:/dev/./urandom", "-jar", "app.jar"]
