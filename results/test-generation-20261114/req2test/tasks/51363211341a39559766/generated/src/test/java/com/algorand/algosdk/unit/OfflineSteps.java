package com.algorand.algosdk.unit;

import com.algorand.algosdk.account.Account;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;

import static org.assertj.core.api.Assertions.assertThat;

public class OfflineSteps {
    private Account account;
    private String convertedMnemonic;

    @Given("mnemonic for private key {string}")
    public void mnemonicForPrivateKey(String mnemonic) throws Exception {
        account = new Account(mnemonic);
    }

    @When("I convert the private key back to a mnemonic")
    public void convertPrivateKeyBackToMnemonic() {
        convertedMnemonic = account.toMnemonic();
    }

    @Then("the mnemonic should still be the same as {string}")
    public void mnemonicShouldStillBeTheSame(String mnemonic) {
        assertThat(convertedMnemonic).isEqualTo(mnemonic);
    }
}
