package com.algorand.algosdk.unit;

import com.algorand.algosdk.crypto.Address;
import com.algorand.algosdk.unit.utils.ClientMocker;
import com.algorand.algosdk.v2.client.algod.AccountInformation;
import com.algorand.algosdk.v2.client.common.AlgodClient;
import com.algorand.algosdk.v2.client.common.Response;
import com.algorand.algosdk.v2.client.model.Account;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;

import java.io.File;

import static org.assertj.core.api.Assertions.assertThat;

public class AlgodResponseSteps {
    private AccountInformation query;
    private Response<Account> response;
    private String error = "";

    @Given("mock http responses in {string} loaded from {string}")
    public void mockHttpResponse(String jsonFile, String directory) throws Exception {
        File body = new File("src/test/resources/" + directory + "/" + jsonFile);
        ClientMocker.oneResponse(200, "application/json", body);

        AlgodClient client = new AlgodClient("http://localhost", 4001, "token");
        ClientMocker.infect(client);
        Address address = new Address();
        query = client.AccountInformation(address);
    }

    @When("we make any Account Information call")
    public void makeAccountInformationCall() {
        try {
            response = query.execute();
        } catch (Exception e) {
            error = e.getMessage() == null ? e.toString() : e.getMessage();
        }
    }

    @Then("expect error string to contain {string}")
    public void expectErrorString(String expected) {
        assertThat(error).contains(expected);
    }

    @Then("the parsed Account Information response should have address {string}")
    public void parsedAccountInformationAddress(String expected) throws Exception {
        assertThat(response).isNotNull();
        assertThat(response.body().address.toString()).isEqualTo(expected);
    }
}
