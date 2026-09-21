package com.eltiootaku01.waifumon;

import com.eltiootaku01.waifumon.contract.EngineRequest;
import com.eltiootaku01.waifumon.contract.EngineResponse;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

final class WaifuMonRuleEngineTest {
    private final ObjectMapper mapper = new ObjectMapper();
    private final WaifuMonRuleEngine engine = new WaifuMonRuleEngine(mapper);

    private EngineRequest request(String command, ObjectNode payload, String idempotencyKey) {
        return new EngineRequest(
            EngineRequest.CURRENT_VERSION,
            "req-" + command,
            "corr-" + command,
            7L,
            -100L,
            command,
            payload,
            idempotencyKey
        );
    }

    @Test
    void contractRejectsMissingIdentityFields() {
        ObjectNode payload = mapper.createObjectNode();
        payload.put("seed", "abc");

        assertThrows(
            IllegalArgumentException.class,
            () -> new EngineRequest("1.0", "", "corr", 7, -100, "gacha.roll", payload, "idem")
        );
    }

    @Test
    void gachaIsDeterministicAndReturnsExplicitRarity() {
        ObjectNode payload = mapper.createObjectNode().put("seed", "same-seed");

        EngineResponse first = engine.execute(request("gacha.roll", payload, "idem-1"));
        EngineResponse second = engine.execute(request("gacha.roll", payload, "idem-1"));

        assertTrue(first.success());
        assertEquals(first.payload().get("rarity").asText(), second.payload().get("rarity").asText());
        assertEquals("same-seed", first.payload().get("seed").asText());
        assertEquals(List.of(), first.eventIds());
        assertEquals(List.of(), first.rewardIds());
    }

    @Test
    void combatIsDeterministicAndValidatesAction() {
        ObjectNode payload = mapper.createObjectNode();
        ObjectNode attacker = mapper.createObjectNode()
            .put("id", "taiga")
            .put("name", "Taiga")
            .put("rarity", "D")
            .put("level", 1);
        ObjectNode defender = mapper.createObjectNode()
            .put("id", "taiga")
            .put("name", "Taiga")
            .put("rarity", "D")
            .put("level", 1);

        payload.set("attacker", attacker);
        payload.set("defender", defender);
        payload.put("action", "attack");
        payload.put("turn_id", "turn-1");

        EngineResponse first = engine.execute(request("combat.resolve", payload, "turn-1"));
        EngineResponse second = engine.execute(request("combat.resolve", payload, "turn-1"));

        assertTrue(first.success());
        assertEquals(first.payload().get("damage").asInt(), second.payload().get("damage").asInt());

        payload.put("action", "invalid");
        EngineResponse invalid = engine.execute(request("combat.resolve", payload, "turn-2"));
        assertFalse(invalid.success());
        assertEquals("IllegalArgumentException", invalid.errorCode());
    }

    @Test
    void progressionResolvesLevelAndEvolutionStageWithoutChangingCopies() {
        ObjectNode payload = mapper.createObjectNode()
            .put("level", 5)
            .put("experience", 495)
            .put("evolution_stage", 1)
            .put("gained", 10)
            .put("copies", 3);

        EngineResponse response = engine.execute(
            request("progression.resolve", payload, "progress-1")
        );

        assertTrue(response.success());
        assertEquals(6, response.payload().get("level").asInt());
        assertEquals(5, response.payload().get("experience").asInt());
        assertEquals(2, response.payload().get("evolution_stage").asInt());
        assertTrue(response.payload().get("evolved").asBoolean());
        assertEquals(3, response.payload().get("copies").asInt());
    }
}
