package com.algorand.algosdk.unit;

import com.algorand.algosdk.crypto.Address;
import com.algorand.algosdk.v2.client.common.IndexerClient;
import com.algorand.algosdk.v2.client.indexer.LookupAccountAssets;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;

import static org.assertj.core.api.Assertions.assertThat;

public class IndexerAccountAssetsPathSteps {
    private LookupAccountAssets query;

    @Given("mock server recording request paths")
    public void mockServerRecordingRequestPaths() {
        // This scenario checks the URL assembled by the query; no request is executed.
    }

    @When("we make a LookupAccountAssets call with accountID {string} assetID {long} includeAll {string} limit {long} next {string}")
    public void makeLookupAccountAssetsCall(String accountId, long assetId, String includeAll,
                                            long limit, String next) {
        IndexerClient client = new IndexerClient("http://localhost", 8980, "");
        query = client.lookupAccountAssets(new Address(accountId))
                .assetId(assetId)
                .includeAll(Boolean.valueOf(includeAll))
                .limit(limit)
                .next(next);
    }

    @Then("expect the path used to be {string}")
    public void expectPath(String expectedPath) {
        assertThat(query).isNotNull();
        assertThat(query.getRequestUrl()).isEqualTo(expectedPath);
    }
}
