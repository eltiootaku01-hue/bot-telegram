package com.eltiootaku01.waifumon.contract;

import com.fasterxml.jackson.databind.JsonNode;

import java.util.List;

public record EngineResponse(
    String requestId,
    boolean success,
    String resultType,
    JsonNode payload,
    long stateVersion,
    List<String> eventIds,
    List<String> rewardIds,
    String errorCode,
    String errorMessage
) {
    public static EngineResponse success(
        String requestId,
        String resultType,
        JsonNode payload,
        long stateVersion,
        List<String> eventIds,
        List<String> rewardIds
    ) {
        return new EngineResponse(
            requestId, true, resultType, payload, stateVersion,
            List.copyOf(eventIds), List.copyOf(rewardIds), null, null
        );
    }

    public static EngineResponse failure(
        String requestId,
        String errorCode,
        String errorMessage
    ) {
        return new EngineResponse(
            requestId, false, "error", null, 0L,
            List.of(), List.of(), errorCode, errorMessage
        );
    }
}
