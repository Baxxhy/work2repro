package com.algorand.algosdk.unit;

import com.algorand.algosdk.v2.client.common.IndexerClient;
import com.algorand.algosdk.v2.client.indexer.SearchForAssets;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;

import java.net.URI;

import static org.assertj.core.api.Assertions.assertThat;

public class IndexerClientV2PathsSteps {
    private IndexerClient client;
    private String actualPath;

    @Given("mock server recording request paths")
    public void mockServerRecordingRequestPaths() {
        // Query URLs can be inspected directly, so no network request is needed.
        client = new IndexerClient("http://localhost", 8080, "");
    }

    @When("we make a SearchForAssets call with limit {int} creator {string} name {string} unit {string} index {int}")
    public void makeSearchForAssetsCall(int limit, String creator, String name, String unit, int index) throws Exception {
        SearchForAssets query = client.searchForAssets();
        if (limit != 0) query.limit((long) limit);
        if (!creator.isEmpty()) query.creator(creator);
        if (!name.isEmpty()) query.name(name);
        if (!unit.isEmpty()) query.unit(unit);
        if (index != 0) query.assetId((long) index);

        URI requestUri = URI.create(query.getRequestUrl());
        actualPath = requestUri.getRawPath();
        if (requestUri.getRawQuery() != null) {
            actualPath += "?" + requestUri.getRawQuery();
        }
    }

    @Then("expect the path used to be {string}")
    public void expectPath(String expectedPath) {
        assertThat(actualPath).isEqualTo(expectedPath);
    }
}
