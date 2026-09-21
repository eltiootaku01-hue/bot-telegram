package com.eltiootaku01.waifumon;

import com.eltiootaku01.waifumon.contract.EngineRequest;
import com.eltiootaku01.waifumon.contract.EngineResponse;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.List;

public final class WaifuMonRuleEngine {
    private static final int MAX_LEVEL = 30;
    private static final double[] GACHA_THRESHOLDS = {
        0.0005, 0.002, 0.007, 0.02, 0.06, 0.30
    };
    private static final String[] GACHA_RARITIES = {
        "SSS", "SS", "S", "A", "B", "C", "D"
    };

    private final ObjectMapper mapper;
    private final java.util.Map<String, CachedResponse> idempotencyCache =
        new java.util.LinkedHashMap<>(256, 0.75f, true);

    public WaifuMonRuleEngine(ObjectMapper mapper) {
        this.mapper = mapper;
    }

    public synchronized EngineResponse execute(EngineRequest request) {
        String fingerprint = request.command() + "|" + request.payload().toString();
        CachedResponse cached = idempotencyCache.get(request.idempotencyKey());
        if (cached != null) {
            if (!cached.fingerprint().equals(fingerprint)) {
                return EngineResponse.failure(
                    request.requestId(),
                    "IDEMPOTENCY_CONFLICT",
                    "Idempotency key was already used with a different request"
                );
            }
            return cached.responseFor(request.requestId());
        }

        EngineResponse response;
        try {
            response = switch (request.command()) {
                case "gacha.roll" -> gachaRoll(request);
                case "combat.resolve" -> combatResolve(request);
                case "progression.resolve" -> progressionResolve(request);
                default -> EngineResponse.failure(
                    request.requestId(),
                    "UNKNOWN_COMMAND",
                    "Unsupported command: " + request.command()
                );
            };
        } catch (IllegalArgumentException ex) {
            response = EngineResponse.failure(
                request.requestId(),
                "INVALID_REQUEST",
                ex.getMessage() == null ? "Invalid WaifuMon request" : ex.getMessage()
            );
        }
        putCached(request.idempotencyKey(), fingerprint, response);
        return response;
    }

    private void putCached(String key, String fingerprint, EngineResponse response) {
        idempotencyCache.put(key, new CachedResponse(fingerprint, response));
        while (idempotencyCache.size() > 10_000) {
            idempotencyCache.remove(idempotencyCache.keySet().iterator().next());
        }
    }

    private record CachedResponse(String fingerprint, EngineResponse response) {
        private EngineResponse responseFor(String requestId) {
            return new EngineResponse(
                requestId,
                response.success(),
                response.resultType(),
                response.payload() == null ? null : response.payload().deepCopy(),
                response.stateVersion(),
                response.eventIds(),
                response.rewardIds(),
                response.errorCode(),
                response.errorMessage()
            );
        }
    }

    private EngineResponse gachaRoll(EngineRequest request) {
        String seed = requiredText(request.payload(), "seed");
        double roll = deterministicUnit("gacha:" + seed);
        String rarity = "D";
        for (int i = 0; i < GACHA_THRESHOLDS.length; i++) {
            if (roll < GACHA_THRESHOLDS[i]) {
                rarity = GACHA_RARITIES[i];
                break;
            }
        }

        ObjectNode payload = mapper.createObjectNode();
        payload.put("rarity", rarity);
        payload.put("seed", seed);
        return EngineResponse.success(
            request.requestId(), "gacha_roll", payload, 0L, List.of(), List.of()
        );
    }

    private EngineResponse combatResolve(EngineRequest request) {
        JsonNode payload = request.payload();
        JsonNode attacker = requiredObject(payload, "attacker");
        JsonNode defender = requiredObject(payload, "defender");
        String action = requiredText(payload, "action");
        String turnId = requiredText(payload, "turn_id");

        int level = positiveInt(attacker, "level");
        String attackerId = requiredText(attacker, "id");
        String defenderId = requiredText(defender, "id");
        String attackerName = requiredText(attacker, "name");
        String defenderName = requiredText(defender, "name");
        String rarity = requiredText(attacker, "rarity");

        int power = switch (action) {
            case "attack" -> 10;
            case "defend" -> 0;
            case "special" -> 18;
            default -> throw new IllegalArgumentException("Unknown combat action: " + action);
        };

        int damage;
        boolean critical = false;
        if ("defend".equals(action)) {
            damage = 0;
        } else {
            byte[] digest = sha256(turnId + ":" + attackerId + ":" + defenderId);
            int variance = Math.floorMod(readInt(digest, 0), 6) - 2;
            critical = (Byte.toUnsignedInt(digest[4]) / 256.0) < 0.08;
            double multiplier = switch (rarity) {
                case "D" -> 1.00;
                case "C" -> 1.10;
                case "B" -> 1.25;
                case "A" -> 1.50;
                case "S" -> 1.80;
                case "SS" -> 2.20;
                case "SSS" -> 2.60;
                default -> throw new IllegalArgumentException("Unknown rarity: " + rarity);
            };
            int base = power + level * 2 + variance;
            damage = Math.max(1, (int) (base * multiplier));
            if (critical) {
                damage *= 2;
            }
        }

        ObjectNode result = mapper.createObjectNode();
        result.put("attacker", attackerName);
        result.put("defender", defenderName);
        result.put("damage", damage);
        result.put("action", action);
        result.put("critical", critical && !"defend".equals(action));
        result.put("defender_hp", Math.max(0, 100 - damage));
        return EngineResponse.success(
            request.requestId(), "combat_result", result, 0L, List.of(), List.of()
        );
    }

    private EngineResponse progressionResolve(EngineRequest request) {
        JsonNode payload = request.payload();
        int level = boundedInt(payload, "level", 1, MAX_LEVEL);
        int experience = Math.max(0, payload.path("experience").asInt());
        int stage = Math.max(1, payload.path("evolution_stage").asInt());
        int gained = nonNegativeInt(payload, "gained");
        int copies = positiveInt(payload, "copies");

        int currentLevel = level;
        int remainingExperience = experience + gained;
        int oldStage = stageForLevel(currentLevel);

        while (currentLevel < MAX_LEVEL && remainingExperience >= currentLevel * 100) {
            remainingExperience -= currentLevel * 100;
            currentLevel += 1;
        }
        if (currentLevel >= MAX_LEVEL) {
            currentLevel = MAX_LEVEL;
            remainingExperience = 0;
        }

        int newStage = stageForLevel(currentLevel);

        ObjectNode result = mapper.createObjectNode();
        result.put("level", currentLevel);
        result.put("experience", remainingExperience);
        result.put("evolution_stage", newStage);
        result.put("evolved", newStage != oldStage);
        result.put("copies", copies);
        return EngineResponse.success(
            request.requestId(), "progression_result", result, 0L, List.of(), List.of()
        );
    }

    private static int stageForLevel(int level) {
        if (level <= 5) return 1;
        if (level <= 10) return 2;
        if (level <= 20) return 3;
        return 4;
    }

    private static String requiredText(JsonNode object, String field) {
        JsonNode value = object.get(field);
        if (value == null || !value.isTextual() || value.asText().isBlank()) {
            throw new IllegalArgumentException(field + " is required");
        }
        return value.asText();
    }

    private static JsonNode requiredObject(JsonNode object, String field) {
        JsonNode value = object.get(field);
        if (value == null || !value.isObject()) {
            throw new IllegalArgumentException(field + " must be an object");
        }
        return value;
    }

    private static int positiveInt(JsonNode object, String field) {
        int value = object.path(field).asInt(Integer.MIN_VALUE);
        if (value <= 0) {
            throw new IllegalArgumentException(field + " must be positive");
        }
        return value;
    }

    private static int nonNegativeInt(JsonNode object, String field) {
        int value = object.path(field).asInt(Integer.MIN_VALUE);
        if (value < 0) {
            throw new IllegalArgumentException(field + " must be non-negative");
        }
        return value;
    }

    private static int boundedInt(JsonNode object, String field, int min, int max) {
        int value = object.path(field).asInt(Integer.MIN_VALUE);
        if (value < min || value > max) {
            throw new IllegalArgumentException(field + " must be between " + min + " and " + max);
        }
        return value;
    }

    private static double deterministicUnit(String seed) {
        byte[] digest = sha256(seed);
        long value = 0;
        for (int i = 0; i < 8; i++) {
            value = (value << 8) | Byte.toUnsignedLong(digest[i]);
        }
        return (value >>> 11) * 0x1.0p-53;
    }

    private static byte[] sha256(String value) {
        try {
            return MessageDigest.getInstance("SHA-256")
                .digest(value.getBytes(StandardCharsets.UTF_8));
        } catch (Exception ex) {
            throw new IllegalStateException("SHA-256 unavailable", ex);
        }
    }

    private static int readInt(byte[] bytes, int offset) {
        return ((bytes[offset] & 0xff) << 24)
            | ((bytes[offset + 1] & 0xff) << 16)
            | ((bytes[offset + 2] & 0xff) << 8)
            | (bytes[offset + 3] & 0xff);
    }
}
