package com.algorand.algosdk.unit;

import com.algorand.algosdk.unit.utils.ClientMocker;
import com.algorand.algosdk.v2.client.common.IndexerClient;
import com.algorand.algosdk.v2.client.common.Response;
import com.algorand.algosdk.v2.client.indexer.SearchForAssets;
import com.algorand.algosdk.v2.client.model.AssetsResponse;
import io.cucumber.java.en.And;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;

import java.io.File;

import static org.assertj.core.api.Assertions.assertThat;

public class IndexerAssetsResponseSteps {
    private File responseFile;
    private Response<AssetsResponse> response;

    @Given("mock http responses in {string} loaded from {string}")
    public void mockHttpResponses(String jsonFile, String directory) {
        responseFile = new File("src/test/resources/" + directory + "/" + jsonFile);
    }

    @When("we make any SearchForAssets call")
    public void makeSearchForAssetsCall() throws Exception {
        ClientMocker.oneResponse(200, "application/json", responseFile);
        IndexerClient client = new IndexerClient("http://localhost", 8980, "token");
        ClientMocker.infect(client);
        SearchForAssets query = client.searchForAssets();
        response = query.execute();
    }

    @Then("expect error string to contain {string}")
    public void expectErrorString(String expected) {
        assertThat(response.message()).contains(expected);
    }

    @And("the parsed SearchForAssets response should be valid on round {long} and the array should be of len {int} and the element at index {int} should have asset index {long}")
    public void verifySearchForAssetsResponse(long round, int length, int index, long assetIndex) {
        AssetsResponse body = response.body();
        assertThat(body.currentRound).isEqualTo(round);
        assertThat(body.assets).hasSize(length);
        assertThat(body.assets.get(index).index).isEqualTo(assetIndex);
    }
}
