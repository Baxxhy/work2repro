package com.algorand.algosdk.unit;

import com.algorand.algosdk.unit.utils.ClientMocker;
import com.algorand.algosdk.v2.client.common.IndexerClient;
import com.algorand.algosdk.v2.client.common.Response;
import com.algorand.algosdk.v2.client.indexer.LookupAssetByID;
import com.algorand.algosdk.v2.client.model.AssetResponse;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;

import java.io.File;

import static org.assertj.core.api.Assertions.assertThat;

public class IndexerClientV2ResponseSteps {
    private IndexerClient client;
    private Response<AssetResponse> response;

    @Given("mock http responses in {string} loaded from {string}")
    public void mockHttpResponse(String jsonFile, String directory) throws Exception {
        File body = new File("src/test/resources/" + directory + "/" + jsonFile);
        ClientMocker.oneResponse(200, "application/json; charset=utf-8", body);
        client = new IndexerClient("localhost", 8980, "");
        ClientMocker.infect(client);
    }

    @When("we make any LookupAssetByID call")
    public void makeLookupAssetByIdCall() throws Exception {
        LookupAssetByID query = client.lookupAssetByID(163650L);
        response = query.execute();
    }

    @Then("expect error string to contain {string}")
    public void expectErrorString(String expected) {
        String actual = response.message();
        assertThat(actual == null ? "" : actual).contains(expected);
    }

    @Then("the parsed LookupAssetByID response should have index {long}")
    public void parsedLookupAssetByIdShouldHaveIndex(long index) {
        assertThat(response.body().asset.index).isEqualTo(index);
    }
}
