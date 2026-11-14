package com.algorand.algosdk.unit;

import com.algorand.algosdk.unit.utils.ClientMocker;
import com.algorand.algosdk.v2.client.common.IndexerClient;
import com.algorand.algosdk.v2.client.common.Response;
import com.algorand.algosdk.v2.client.indexer.LookupAssetTransactions;
import com.algorand.algosdk.v2.client.model.TransactionsResponse;
import io.cucumber.java.en.And;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;

import java.io.File;

import static org.assertj.core.api.Assertions.assertThat;

public class LookupAssetTransactionsSteps {
    private IndexerClient client;
    private Response<TransactionsResponse> response;

    @Given("mock http responses in {string} loaded from {string}")
    public void mockHttpResponse(String jsonFile, String directory) throws Exception {
        client = new IndexerClient("http://localhost", 8980, "");
        ClientMocker.infect(client);
        ClientMocker.oneResponse(200, "application/json",
                new File("src/test/resources/" + directory, jsonFile));
    }

    @When("we make any LookupAssetTransactions call")
    public void lookupAssetTransactions() throws Exception {
        response = client.lookupAssetTransactions(163650L).execute();
    }

    @Then("expect error string to contain {string}")
    public void expectErrorString(String error) {
        assertThat(response).isNotNull();
        if (error.isEmpty()) {
            assertThat(response.isSuccessful()).isTrue();
        } else {
            assertThat(response.message()).contains(error);
        }
    }

    @And("the parsed LookupAssetTransactions response should be valid on round {long}, and contain an array of len {int} and element number {int} should have sender {string}")
    public void verifyTransactions(long round, int length, int index, String sender) {
        TransactionsResponse body = response.body();
        assertThat(body.currentRound).isEqualTo(round);
        assertThat(body.transactions).hasSize(length);
        assertThat(body.transactions.get(index).sender).isEqualTo(sender);
    }
}
