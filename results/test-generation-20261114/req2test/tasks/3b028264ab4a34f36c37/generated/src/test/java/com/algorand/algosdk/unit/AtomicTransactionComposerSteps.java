package com.algorand.algosdk.unit;

import com.algorand.algosdk.account.Account;
import com.algorand.algosdk.transaction.AtomicTransactionComposer;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;

import static org.assertj.core.api.Assertions.assertThat;

public class AtomicTransactionComposerSteps {
    private Account signingAccount;
    private AtomicTransactionComposer composer;

    @Given("a signing account with address {string} and mnemonic {string}")
    public void signingAccount(String address, String mnemonic) throws Exception {
        signingAccount = new Account(mnemonic);
        assertThat(signingAccount.getAddress().toString()).isEqualTo(address);
    }

    @Given("a new AtomicTransactionComposer")
    public void newComposer() {
        composer = new AtomicTransactionComposer();
    }

    @When("I build the transaction group with the composer. If there is an error it is {string}.")
    public void buildGroupExpectingError(String expectedError) {
        try {
            composer.buildGroup();
            throw new AssertionError("Expected buildGroup to fail for an empty transaction group (" + expectedError + ")");
        } catch (AssertionError e) {
            throw e;
        } catch (Exception e) {
            assertThat(e).isNotNull();
        }
    }

    @Then("The composer should have a status of {string}.")
    public void composerStatus(String status) {
        assertThat(composer.getStatus().name()).isEqualTo(status);
    }
}
