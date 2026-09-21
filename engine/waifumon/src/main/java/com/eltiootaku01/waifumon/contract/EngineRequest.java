package com.eltiootaku01.waifumon.contract;

import com.fasterxml.jackson.databind.JsonNode;

public record EngineRequest(
    String contractVersion,
    String requestId,
    String correlationId,
    long playerId,
    long communityId,
    String command,
    JsonNode payload,
    String idempotencyKey
) {
    public static final String CURRENT_VERSION = "1.0";

    public EngineRequest {
        if (!CURRENT_VERSION.equals(contractVersion)) {
            throw new IllegalArgumentException("Unsupported contract version: " + contractVersion);
        }
        if (requestId == null || requestId.isBlank()) {
            throw new IllegalArgumentException("request_id is required");
        }
        if (correlationId == null || correlationId.isBlank()) {
            throw new IllegalArgumentException("correlation_id is required");
        }
        if (command == null || command.isBlank()) {
            throw new IllegalArgumentException("command is required");
        }
        if (idempotencyKey == null || idempotencyKey.isBlank()) {
            throw new IllegalArgumentException("idempotency_key is required");
        }
        if (payload == null || !payload.isObject()) {
            throw new IllegalArgumentException("payload must be a JSON object");
        }
    }
}
