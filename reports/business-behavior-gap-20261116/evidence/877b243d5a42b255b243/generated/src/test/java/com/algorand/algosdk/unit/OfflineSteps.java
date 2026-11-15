package com.algorand.algosdk.unit;

import com.algorand.algosdk.account.Account;
import com.algorand.algosdk.crypto.Address;
import io.cucumber.java.en.When;
import io.cucumber.java.en.Then;

import static org.assertj.core.api.Assertions.assertThat;

public class OfflineSteps {
    private Account account;
    private String originalAddress;
    private Address decodedAddress;
    private String encodedAddress;

    @When("I generate a key")
    public void generateKey() throws Exception {
        account = new Account();
        originalAddress = account.getAddress().toString();
    }

    @When("I decode the address")
    public void decodeAddress() throws Exception {
        decodedAddress = new Address(originalAddress);
    }

    @When("I encode the address")
    public void encodeAddress() {
        encodedAddress = decodedAddress.toString();
    }

    @Then("the address should still be the same")
    public void addressShouldStillBeTheSame() {
        assertThat(encodedAddress).isEqualTo(originalAddress);
    }
}
