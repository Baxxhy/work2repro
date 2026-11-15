package com.algorand.algosdk.unit;

import com.algorand.algosdk.crypto.Address;
import com.algorand.algosdk.v2.client.algod.AccountApplicationInformation;
import com.algorand.algosdk.v2.client.common.AlgodClient;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;

import java.net.URI;

import static org.assertj.core.api.Assertions.assertThat;

public class AlgodRestApiV2PathsSteps {
    private AccountApplicationInformation query;
    private String recordedPath;

    @Given("mock server recording request paths")
    public void mockServerRecordingRequestPaths() {
        // The path-generation check does not need a live server; retain the URL
        // produced by the query as the recorded request path.
        recordedPath = null;
    }

    @When("we make an Account Application Information call against account {string} applicationID {int}")
    public void makeAccountApplicationInformationCall(String account, int applicationId) throws Exception {
        AlgodClient client = new AlgodClient("http://localhost", 4001, "");
        query = client.AccountApplicationInformation(new Address(account), (long) applicationId);
        URI uri = URI.create(query.getRequestUrl());
        recordedPath = uri.getRawPath();
        if (uri.getRawQuery() != null) {
            recordedPath += "?" + uri.getRawQuery();
        }
    }

    @Then("expect the path used to be {string}")
    public void expectPathUsedToBe(String expectedPath) {
        assertThat(recordedPath).isEqualTo(expectedPath);
    }
}
