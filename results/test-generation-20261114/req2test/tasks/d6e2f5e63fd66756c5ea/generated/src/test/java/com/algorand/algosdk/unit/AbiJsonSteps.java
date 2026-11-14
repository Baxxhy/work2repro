package com.algorand.algosdk.unit;

import com.algorand.algosdk.abi.Method;
import com.algorand.algosdk.util.Encoder;
import io.cucumber.java.en.And;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;

import static org.assertj.core.api.Assertions.assertThat;

public class AbiJsonSteps {
    private Method method;
    private String serializedJson;
    private Method deserializedMethod;

    @When("I create the Method object with name {string} first argument name {string} first argument type {string} second argument name {string} second argument type {string} and return type {string}")
    public void createMethodWithArgumentNames(String name, String firstArgName, String firstArgType,
                                              String secondArgName, String secondArgType, String returnType) {
        method = new Method(name, null,
                Arrays.asList(new Method.Arg(firstArgName, firstArgType, null),
                        new Method.Arg(secondArgName, secondArgType, null)),
                new Method.Returns(returnType, null));
    }

    @And("I serialize the Method object into json")
    public void serializeMethod() throws IOException {
        serializedJson = Encoder.encodeToJson(method);
        deserializedMethod = Encoder.decodeFromJson(serializedJson, Method.class);
    }

    @Then("the produced json should equal {string} loaded from {string}")
    public void producedJsonShouldEqualFixture(String jsonFile, String directory) throws IOException {
        String resource = "/com/algorand/algosdk/unit/" + directory + "/" + jsonFile;
        try (InputStream input = getClass().getResourceAsStream(resource)) {
            assertThat(input).as("fixture resource %s", resource).isNotNull();
            String expected = new String(input.readAllBytes(), StandardCharsets.UTF_8).trim();
            assertThat(serializedJson).isEqualTo(expected);
        }
    }

    @And("the deserialized json should equal the original Method object")
    public void deserializedJsonShouldEqualOriginalMethod() {
        assertThat(deserializedMethod).isEqualTo(method);
    }
}
