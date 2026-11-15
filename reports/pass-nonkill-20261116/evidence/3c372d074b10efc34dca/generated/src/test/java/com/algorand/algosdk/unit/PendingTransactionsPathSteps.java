package com.algorand.algosdk.unit;

import com.algorand.algosdk.unit.utils.TestingUtils;
import com.algorand.algosdk.v2.client.algod.GetPendingTransactions;
import com.algorand.algosdk.v2.client.common.AlgodClient;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;

import static org.assertj.core.api.Assertions.assertThat;

public class PendingTransactionsPathSteps {
    private final ScenarioState state;

    public PendingTransactionsPathSteps(ScenarioState state) {
        this.state = state;
    }

    @Given("mock server recording request paths")
    public void mockServerRecordingRequestPaths() {
        // The query exposes its fully constructed request URL; no request needs to be sent.
        state.client = new AlgodClient("http://localhost", 4001, "");
    }

    @When("we make a Pending Transaction Information with max {long} and format {string}")
    public void makePendingTransactionInformation(long max, String format) {
        assertThat(format).isEqualTo("msgpack");
        GetPendingTransactions query = state.client.GetPendingTransactions();
        if (TestingUtils.notEmpty(max)) {
            query.max(max);
        }
        state.requestUrl = query.getRequestUrl();
    }

    @Then("expect the path used to be {string}")
    public void expectPath(String expectedPath) {
        TestingUtils.verifyPathUrls(state.requestUrl, expectedPath);
    }

    public static class ScenarioState {
        private AlgodClient client;
        private String requestUrl;
    }
}
