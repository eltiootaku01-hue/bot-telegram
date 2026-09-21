package com.eltiootaku01.waifumon;

import com.eltiootaku01.waifumon.contract.EngineRequest;
import com.eltiootaku01.waifumon.contract.EngineResponse;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertTrue;

final class ProtocolSmokeTest {
    @Test
    void requestAndResponseRoundTripAsJson() throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        ObjectNode payload = mapper.createObjectNode().put("seed", "smoke");

        EngineRequest request = new EngineRequest(
            EngineRequest.CURRENT_VERSION,
            "request-1",
            "correlation-1",
            1L,
            2L,
            "gacha.roll",
            payload,
            "idempotency-1"
        );

        String wire = mapper.writeValueAsString(request);
        EngineRequest decoded = mapper.readValue(wire, EngineRequest.class);
        EngineResponse response = new WaifuMonRuleEngine(mapper).execute(decoded);

        assertTrue(response.success());
    }
}
