package com.algorand.algosdk.unit;

import com.algorand.algosdk.v2.client.common.IndexerClient;
import com.algorand.algosdk.v2.client.indexer.SearchForAccounts;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;

import java.net.URI;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Step definitions for the Indexer client path feature.
 */
public class IndexerClientV2PathsSteps {
    private final ScenarioState state;

    public IndexerClientV2PathsSteps(ScenarioState state) {
        this.state = state;
    }

    @Given("mock server recording request paths")
    public void mockServerRecordingRequestPaths() {
        // No network request is needed: Query.getRequestUrl exposes the URL that
        // the client would send to the server.
        state.client = new IndexerClient("http://localhost", 8980, "");
    }

    @When("we make a Search Accounts call with assetID {long} limit {long} currencyGreaterThan {long} currencyLessThan {long} and round {long}")
    public void searchAccounts(long assetId, long limit, long currencyGreaterThan,
                              long currencyLessThan, long round) {
        SearchForAccounts query = state.client.searchForAccounts()
                .assetId(assetId)
                .limit(limit)
                .currencyGreaterThan(currencyGreaterThan)
                .currencyLessThan(currencyLessThan)
                .round(round);
        state.path = pathAndQuery(query.getRequestUrl());
    }

    @Then("expect the path used to be {string}")
    public void expectPath(String expectedPath) {
        assertThat(state.path).isEqualTo(expectedPath);
    }

    private static String pathAndQuery(String url) {
        URI uri = URI.create(url);
        String path = uri.getRawPath();
        return uri.getRawQuery() == null ? path : path + "?" + uri.getRawQuery();
    }

    public static class ScenarioState {
        private IndexerClient client;
        private String path;
    }
}
