package com.algorand.algosdk.unit;

import com.algorand.algosdk.account.Account;
import com.algorand.algosdk.crypto.Address;
import com.algorand.algosdk.crypto.Signature;
import com.algorand.algosdk.util.Encoder;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.When;
import io.cucumber.java.en.Then;

import java.security.GeneralSecurityException;
import java.util.Base64;

import static org.assertj.core.api.Assertions.assertThat;

public class TealSignSteps {
    private byte[] data;
    private byte[] privateKey;
    private Address contractAddress;
    private Signature signature;

    @Given("base64 encoded data to sign {string}")
    public void dataToSign(String encoded) {
        data = Encoder.decodeFromBase64(encoded);
    }

    @Given("program hash {string}")
    public void programHash(String hash) throws GeneralSecurityException {
        contractAddress = new Address(hash);
    }

    @Given("base64 encoded private key {string}")
    public void privateKey(String encoded) {
        privateKey = Encoder.decodeFromBase64(encoded);
    }

    @When("I perform tealsign")
    public void performTealSign() throws Exception {
        signature = new Account(privateKey).tealSign(data, contractAddress);
    }

    @Then("the signature should be equal to {string}")
    public void signatureShouldEqual(String expected) {
        assertThat(Base64.getEncoder().encodeToString(signature.getBytes())).isEqualTo(expected);
    }
}
