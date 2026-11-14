package com.algorand.algosdk.unit;

import com.algorand.algosdk.crypto.Address;
import com.algorand.algosdk.unit.utils.TestingUtils;
import com.algorand.algosdk.v2.client.common.AlgodClient;
import com.algorand.algosdk.v2.client.common.Query;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;

public class AccountAssetsInformationPathSteps {
    private Query query;

    @Given("mock server recording request paths")
    public void mockServerRecordingRequestPaths() {
        // This scenario checks the URL assembled by the query; no request needs to be sent.
    }

    @When("we make an Account Assets Information call against account {string} with limit {long} and next {string}")
    public void makeAccountAssetsInformationCall(String account, long limit, String next) {
        AlgodClient client = new AlgodClient("http://localhost", 4001, "");
        query = client.AccountAssetsInformation(new Address(account))
                .limit(limit)
                .next(next);
    }

    @Then("expect the path used to be {string}")
    public void expectPathUsed(String expectedPath) {
        TestingUtils.verifyPathUrls(query.getRequestUrl(), expectedPath);
    }
}
