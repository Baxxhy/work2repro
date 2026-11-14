package com.algorand.algosdk.unit;

import com.algorand.algosdk.v2.client.common.IndexerClient;
import com.algorand.algosdk.v2.client.indexer.SearchForApplications;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;

import static org.assertj.core.api.Assertions.assertThat;

public class IndexerClientPathsSteps {
    private IndexerClient client;
    private SearchForApplications query;

    @Given("mock server recording request paths")
    public void mockServerRecordingRequestPaths() {
        client = new IndexerClient("http://localhost", 8980, "");
    }

    @When("we make a SearchForApplications call with applicationID {long}")
    public void searchForApplications(long applicationId) {
        query = client.searchForApplications().applicationId(applicationId);
    }

    @Then("expect the path used to be {string}")
    public void expectPath(String expectedPath) {
        assertThat(query.getRequestUrl()).endsWith(expectedPath);
    }
}
