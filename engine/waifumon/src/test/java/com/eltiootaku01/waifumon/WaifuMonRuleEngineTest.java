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

    private EngineRequest request(
        String command,
        ObjectNode payload,
        String idempotencyKey
    ) {
        return request(command, payload, idempotencyKey, "req-" + command);
    }

    private EngineRequest request(
        String command,
        ObjectNode payload,
        String idempotencyKey,
        String requestId
    ) {
        return new EngineRequest(
            EngineRequest.CURRENT_VERSION,
            requestId,
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
        assertEquals("INVALID_REQUEST", invalid.errorCode());
    }

    @Test
    void idempotencyKeyReplaysTheSameResultAndRejectsConflicts() {
        ObjectNode payload = mapper.createObjectNode().put("seed", "idem-seed");

        EngineResponse first = engine.execute(request("gacha.roll", payload, "idem-key"));
        EngineResponse replay = engine.execute(
            request("gacha.roll", payload, "idem-key", "req-gacha-replay")
        );

        assertTrue(first.success());
        assertTrue(replay.success());
        assertEquals(first.payload().get("rarity").asText(), replay.payload().get("rarity").asText());
        assertNotEquals(first.requestId(), replay.requestId());

        ObjectNode conflictingPayload = mapper.createObjectNode().put("seed", "other-seed");
        EngineResponse conflict = engine.execute(request("gacha.roll", conflictingPayload, "idem-key"));

        assertFalse(conflict.success());
        assertEquals("IDEMPOTENCY_CONFLICT", conflict.errorCode());
    }



    @Test
    void gachaResolutionOwnsPityAndCharacterSelection() {
        ObjectNode candidates = mapper.createArrayNode()
            .add(mapper.createObjectNode().put("id", "zeta").put("rarity", "D"))
            .add(mapper.createObjectNode().put("id", "alpha").put("rarity", "D"))
            .add(mapper.createObjectNode().put("id", "beta").put("rarity", "C"));
        ObjectNode payload = mapper.createObjectNode()
            .put("seed", "gacha-pity")
            .put("d_streak", 6);
        payload.set("candidates", candidates);
        payload.set("owned_character_ids", mapper.createArrayNode().add("alpha"));

        EngineResponse response = engine.execute(
            request("gacha.resolve", payload, "gacha-pity")
        );

        assertTrue(response.success());
        assertTrue(
            response.payload().get("rolled_rarity").asText().equals("C")
                || response.payload().get("rolled_rarity").asText().equals("D")
        );
        if (response.payload().get("pity_triggered").asBoolean()) {
            assertEquals("C", response.payload().get("rolled_rarity").asText());
            assertEquals(0, response.payload().get("d_streak").asInt());
            assertEquals("beta", response.payload().get("character_id").asText());
        }
    }

    @Test
    void evolutionResolutionReturnsAuthoritativeStageBounds() {
        ObjectNode payload = mapper.createObjectNode().put("level", 21);

        EngineResponse response = engine.execute(
            request("evolution.resolve", payload, "evolution-21")
        );

        assertTrue(response.success());
        assertEquals(4, response.payload().get("evolution_stage").asInt());
        assertEquals(21, response.payload().get("min_level").asInt());
        assertEquals(30, response.payload().get("max_level").asInt());
        assertEquals(0, response.payload().get("next_level").asInt());
    }

    @Test
    void potentialAndElementStyleAreStableRules() {
        ObjectNode potentialPayload = mapper.createObjectNode().put("potential_seed", "seed-42");
        EngineResponse potential = engine.execute(
            request("potential.resolve", potentialPayload, "potential-42")
        );
        EngineResponse potentialReplay = engine.execute(
            request("potential.resolve", potentialPayload, "potential-42", "potential-replay")
        );

        ObjectNode stylePayload = mapper.createObjectNode().put("element", "rayo");
        EngineResponse style = engine.execute(
            request("style.resolve", stylePayload, "style-rayo")
        );

        assertTrue(potential.success());
        assertEquals(
            potential.payload().get("potential_score").asInt(),
            potentialReplay.payload().get("potential_score").asInt()
        );
        assertTrue(style.success());
        assertEquals("ataque explosivo", style.payload().get("style").asText());
    }

    @Test
    void statsResolutionReturnsAllGameplayFields() {
        ObjectNode character = mapper.createObjectNode()
            .put("id", "test-waifu")
            .put("name", "Test Waifu")
            .put("element", "aire")
            .put("power_score", 50);
        ObjectNode payload = mapper.createObjectNode()
            .set("character", character);
        payload.put("level", 12);
        payload.put("rarity", "B");
        payload.put("potential_seed", "stats-seed");

        EngineResponse response = engine.execute(
            request("stats.resolve", payload, "stats-12")
        );

        assertTrue(response.success());
        assertEquals(12, response.payload().get("level").asInt());
        assertEquals("B", response.payload().get("rarity").asText());
        assertEquals(3, response.payload().get("evolution_stage").asInt());
        assertEquals("velocidad", response.payload().get("style").asText());
        assertTrue(response.payload().get("max_hp").asInt() > 0);
        assertTrue(response.payload().get("strength").asInt() > 0);
        assertTrue(response.payload().get("critical_rate").asInt() <= 95);
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
