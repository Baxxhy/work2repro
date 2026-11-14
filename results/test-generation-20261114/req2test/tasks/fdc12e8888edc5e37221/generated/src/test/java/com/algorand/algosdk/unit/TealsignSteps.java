package com.algorand.algosdk.unit;

import com.algorand.algosdk.account.Account;
import com.algorand.algosdk.crypto.Signature;
import com.algorand.algosdk.util.Encoder;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;

import static org.assertj.core.api.Assertions.assertThat;

public class TealsignSteps {
    private byte[] data;
    private byte[] program;
    private Account account;
    private Signature signature;

    @Given("base64 encoded data to sign {string}")
    public void dataToSign(String encoded) {
        data = Encoder.decodeFromBase64(encoded);
    }

    @Given("base64 encoded program {string}")
    public void program(String encoded) {
        program = Encoder.decodeFromBase64(encoded);
    }

    @Given("mnemonic for private key {string}")
    public void mnemonic(String mnemonic) throws Exception {
        account = new Account(mnemonic);
    }

    @When("I perform tealsign")
    public void performTealsign() throws Exception {
        signature = account.tealSignFromProgram(data, program);
    }

    @Then("the signature should be equal to {string}")
    public void signatureShouldEqual(String expected) {
        assertThat(Encoder.encodeToBase64(signature.getBytes())).isEqualTo(expected);
    }
}
