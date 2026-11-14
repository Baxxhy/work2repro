package com.algorand.algosdk.unit;

import com.algorand.algosdk.v2.client.algod.GetBlock;
import com.algorand.algosdk.v2.client.common.AlgodClient;
import com.algorand.algosdk.v2.client.common.QueryData;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;

import java.net.URL;

import static org.assertj.core.api.Assertions.assertThat;

public class AlgodBlockHeaderPathSteps {
    private AlgodClient client;
    private String requestPath;

    @Given("mock server recording request paths")
    public void mockServerRecordingRequestPaths() {
        client = new AlgodClient("http://localhost", 4001, "");
    }

    @When("we make a Get Block call for round {long} with format {string} and header-only {string}")
    public void makeGetBlockCall(long round, String format, String headerOnly) throws Exception {
        GetBlock query = client.GetBlock(round);
        // GetBlock has no format fluent setter; supply the API's format query option.
        java.lang.reflect.Field dataField = query.getClass().getSuperclass().getDeclaredField("qd");
        dataField.setAccessible(true);
        ((QueryData) dataField.get(query)).addQuery("format", format);
        query.headerOnly(Boolean.valueOf(headerOnly));
        URL url = new URL(query.getRequestUrl());
        requestPath = url.getPath() + (url.getQuery() == null ? "" : "?" + url.getQuery());
    }

    @Then("expect the path used to be {string}")
    public void expectPath(String expected) {
        assertThat(requestPath).isEqualTo(expected);
    }
}
