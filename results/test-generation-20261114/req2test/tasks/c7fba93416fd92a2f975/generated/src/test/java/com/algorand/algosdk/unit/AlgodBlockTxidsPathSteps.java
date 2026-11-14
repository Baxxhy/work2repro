package com.algorand.algosdk.unit;

import com.algorand.algosdk.v2.client.algod.GetBlockTxids;
import com.algorand.algosdk.v2.client.common.AlgodClient;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;

import static org.assertj.core.api.Assertions.assertThat;

public class AlgodBlockTxidsPathSteps {
    private AlgodClient client;
    private String requestPath;

    @Given("mock server recording request paths")
    public void mockServerRecordingRequestPaths() {
        // This scenario only inspects the generated request URL; it does not execute a request.
        client = new AlgodClient("localhost", 4001, "test-token");
    }

    @When("we make a GetBlockTxids call against block number {long}")
    public void makeGetBlockTxidsCall(long round) {
        GetBlockTxids query = client.GetBlockTxids(round);
        requestPath = query.getRequestUrl();
    }

    @Then("expect the path used to be {string}")
    public void expectPath(String expectedPath) {
        assertThat(requestPath).isEqualTo(expectedPath);
    }
}
