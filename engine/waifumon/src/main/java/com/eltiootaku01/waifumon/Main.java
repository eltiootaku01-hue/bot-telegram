package com.eltiootaku01.waifumon;

import com.eltiootaku01.waifumon.contract.EngineRequest;
import com.eltiootaku01.waifumon.contract.EngineResponse;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jdk8.Jdk8Module;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;

public final class Main {
    private Main() {
    }

    public static void main(String[] args) throws Exception {
        ObjectMapper mapper = new ObjectMapper()
            .registerModule(new Jdk8Module())
            .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);

        WaifuMonRuleEngine engine = new WaifuMonRuleEngine(mapper);
        BufferedReader reader = new BufferedReader(
            new InputStreamReader(System.in, StandardCharsets.UTF_8)
        );
        PrintWriter writer = new PrintWriter(System.out, true, StandardCharsets.UTF_8);

        String line;
        while ((line = reader.readLine()) != null) {
            if (line.isBlank()) {
                continue;
            }
            try {
                EngineRequest request = mapper.readValue(line, EngineRequest.class);
                EngineResponse response = engine.execute(request);
                writer.println(mapper.writeValueAsString(response));
            } catch (Exception ex) {
                writer.println(mapper.writeValueAsString(
                    EngineResponse.failure(
                        "unknown",
                        ex.getClass().getSimpleName(),
                        ex.getMessage() == null ? "Engine request failed" : ex.getMessage()
                    )
                ));
            }
        }
    }
}
