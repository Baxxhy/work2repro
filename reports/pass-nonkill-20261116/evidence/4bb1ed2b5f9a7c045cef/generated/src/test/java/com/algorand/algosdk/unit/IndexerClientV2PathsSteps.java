package com.algorand.algosdk.unit;

import com.algorand.algosdk.v2.client.common.IndexerClient;
import com.algorand.algosdk.v2.client.indexer.SearchForAccounts;
import com.algorand.algosdk.v2.client.model.Enums;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;

import java.net.URI;
import java.util.ArrayList;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

public class IndexerClientV2PathsSteps {
    private IndexerClient client;
    private String requestUrl;

    @Given("mock server recording request paths")
    public void mockServerRecordingRequestPaths() {
        // The scenario inspects the query URL before execution, so no network server is needed.
        client = new IndexerClient("localhost", 8080, "");
    }

    @When("we make a Search Accounts call with exclude {string}")
    public void searchAccountsWithExclude(String exclude) {
        List<Enums.Exclude> values = new ArrayList<>();
        for (String value : exclude.split(",")) {
            values.add(Enums.Exclude.forValue(value));
        }
        SearchForAccounts query = client.searchForAccounts().exclude(values);
        requestUrl = query.getRequestUrl();
    }

    @Then("expect the path used to be {string}")
    public void expectPath(String expectedPath) throws Exception {
        URI uri = URI.create(requestUrl);
        String actualPath = uri.getRawPath();
        if (uri.getRawQuery() != null) {
            actualPath += "?" + uri.getRawQuery();
        }
        assertThat(actualPath).isEqualTo(expectedPath);
    }
}
