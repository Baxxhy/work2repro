package com.algorand.algosdk.unit;

import com.algorand.algosdk.abi.Interface;
import com.algorand.algosdk.abi.Method;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.cucumber.java.en.And;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.Collections;

import static org.assertj.core.api.Assertions.assertThat;

public class AbiJsonInterfaceSteps {
    private static final ObjectMapper MAPPER = new ObjectMapper();

    private Method method;
    private Interface apiInterface;
    private String serialized;

    @When("I create the Method object from method signature {string}")
    public void createMethodFromSignature(String signature) {
        method = new Method(signature);
    }

    @And("I create an Interface object from the Method object with name {string} and description {string}")
    public void createInterface(String name, String description) {
        apiInterface = new Interface(name, description, Collections.singletonList(method));
    }

    @And("I serialize the Interface object into json")
    public void serializeInterface() throws IOException {
        serialized = MAPPER.writeValueAsString(apiInterface);
    }

    @Then("the produced json should equal {string} loaded from {string}")
    public void compareJsonToFixture(String filename, String directory) throws IOException {
        String fixturePath = "src/test/resources/com/algorand/algosdk/unit/"
                + directory + "/" + filename;
        String fixture = new String(Files.readAllBytes(Paths.get(fixturePath)), "UTF-8");
        JsonNode expected = MAPPER.readTree(fixture);
        JsonNode actual = MAPPER.readTree(serialized);
        assertThat(actual).isEqualTo(expected);
    }

    @And("the deserialized json should equal the original Interface object")
    public void deserializedInterfaceShouldEqualOriginal() throws IOException {
        Interface deserialized = MAPPER.readValue(serialized, Interface.class);
        assertThat(deserialized).isEqualTo(apiInterface);
    }
}
