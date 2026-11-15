package com.algorand.algosdk.unit;

import com.algorand.algosdk.crypto.LogicsigSignature;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;

import java.util.Base64;

import static org.assertj.core.api.Assertions.assertThat;

public class ProgramSanityCheckSteps {
    private byte[] programBytes;
    private Throwable sanityCheckError;

    @Given("a base64 encoded program bytes for heuristic sanity check {string}")
    public void givenBase64ProgramBytes(String encoded) {
        programBytes = Base64.getDecoder().decode(encoded);
    }

    @When("I start heuristic sanity check over the bytes")
    public void startHeuristicSanityCheck() {
        try {
            new LogicsigSignature(programBytes);
        } catch (Throwable error) {
            sanityCheckError = error;
        }
    }

    @Then("if the heuristic sanity check throws an error, the error contains {string}")
    public void checkHeuristicSanityCheckError(String expectedMessage) {
        if (expectedMessage.isEmpty()) {
            assertThat(sanityCheckError).isNull();
        } else {
            assertThat(sanityCheckError).isNotNull();
            assertThat(sanityCheckError.getMessage()).contains(expectedMessage);
        }
    }
}
