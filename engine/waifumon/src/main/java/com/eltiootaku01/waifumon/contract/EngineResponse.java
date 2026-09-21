package com.eltiootaku01.waifumon.contract;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;

import java.util.List;

public record EngineResponse(
    @JsonProperty("request_id") String requestId,
    @JsonProperty("success") boolean success,
    @JsonProperty("result_type") String resultType,
    @JsonProperty("payload") JsonNode payload,
    @JsonProperty("state_version") long stateVersion,
    @JsonProperty("event_ids") List<String> eventIds,
    @JsonProperty("reward_ids") List<String> rewardIds,
    @JsonProperty("error_code") String errorCode,
    @JsonProperty("error_message") String errorMessage
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
