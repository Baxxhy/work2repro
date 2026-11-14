package com.algorand.algosdk.unit;

import com.algorand.algosdk.v2.client.common.IndexerClient;
import com.algorand.algosdk.v2.client.indexer.LookupBlock;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;

import java.net.URI;

import static org.assertj.core.api.Assertions.assertThat;

public class IndexerClientV2PathsSteps {
    private IndexerClient client;
    private LookupBlock lookupBlock;

    @Given("mock server recording request paths")
    public void mockServerRecordingRequestPaths() {
        // URL generation does not execute the query or require a live server.
        client = new IndexerClient("http://localhost", 8080, "");
    }

    @When("we make a Lookup Block call against round {long}")
    public void makeLookupBlockCall(long round) {
        lookupBlock = client.lookupBlock(round);
    }

    @Then("expect the path used to be {string}")
    public void expectPathUsedToBe(String expectedPath) throws Exception {
        assertThat(URI.create(lookupBlock.getRequestUrl()).getPath()).isEqualTo(expectedPath);
    }
}
