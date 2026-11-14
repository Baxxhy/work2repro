package com.algorand.algosdk.unit;

import com.algorand.algosdk.account.Account;
import com.algorand.algosdk.abi.Method;
import com.algorand.algosdk.builder.transaction.MethodCallTransactionBuilder;
import com.algorand.algosdk.builder.transaction.TransactionParametersBuilder;
import com.algorand.algosdk.crypto.TEALProgram;
import com.algorand.algosdk.logic.StateSchema;
import com.algorand.algosdk.transaction.*;
import com.algorand.algosdk.util.Encoder;
import io.cucumber.java.en.*;
import java.math.BigInteger;
import java.nio.file.*;
import java.util.*;
import static org.assertj.core.api.Assertions.assertThat;

public class AtomicComposerSteps {
    Account account;
    AtomicTransactionComposer composer;
    Method method;
    List<Object> args;
    TxnSigner signer;
    long appId;
    MethodCallStepsParams params;

    @Given("a signing account with address {string} and mnemonic {string}")
    public void account(String address, String mnemonic) throws Exception {
        account = new Account(mnemonic);
        assertThat(account.getAddress().toString()).isEqualTo(address);
    }
    @Given("a new AtomicTransactionComposer")
    public void newComposer() { composer = new AtomicTransactionComposer(); }
    @Given("suggested transaction parameters fee {int}, flat-fee {string}, first-valid {int}, last-valid {int}, genesis-hash {string}, genesis-id {string}")
    public void params(int fee, String flat, int first, int last, String hash, String id) {
        params = new MethodCallStepsParams(fee, first, last, Base64.getDecoder().decode(hash), id);
    }
    @Given("an application id {int}")
    public void app(int id) { appId = id; }
    @When("I make a transaction signer for the signing account.")
    public void makeSigner() { signer = account.getTransactionSigner(); }
    @Given("I create the Method object from method signature {string}")
    public void method(String signature) { method = new Method(signature); }
    @Given("I create a new method arguments array.")
    public void newArgs() { args = new ArrayList<>(); }
    @Given("I append the encoded arguments {string} to the method arguments array.")
    public void append(String value) { args.add(Encoder.decodeUint64(Base64.getDecoder().decode(value))); }
    @Given("I add a method call with the signing account, the current application, suggested params, on complete {string}, current transaction signer, current method arguments, approval-program {string}, clear-program {string}, global-bytes {int}, global-ints {int}, local-bytes {int}, local-ints {int}, extra-pages {int}.")
    public void add(String completion, String approval, String clear, int gb, int gi, int lb, int li, int pages) throws Exception {
        MethodCallTransactionBuilder<?> b = MethodCallTransactionBuilder.Builder()
            .sender(account.getAddress()).applicationId(appId).onComplete(Transaction.OnCompletion.String(completion))
            .method(method).methodArguments(args).signer(signer)
            .fee(BigInteger.valueOf(1234)).flatFee(BigInteger.valueOf(1234))
            .firstValid(BigInteger.valueOf(9000)).lastValid(BigInteger.valueOf(9010))
            .genesisHash(params.hash).genesisID(params.id)
            .approvalProgram(new TEALProgram(Files.readAllBytes(Paths.get("src/test/resources", approval))))
            .clearStateProgram(new TEALProgram(Files.readAllBytes(Paths.get("src/test/resources", clear))))
            .globalStateSchema(new StateSchema(gb, gi)).localStateSchema(new StateSchema(lb, li)).extraPages((long)pages);
        composer.addMethodCall(b.build());
    }
    @When("I build the transaction group with the composer. If there is an error it is {string}.")
    public void build(String error) throws Exception { composer.buildGroup(); }
    @Then("The composer should have a status of {string}.")
    public void status(String expected) { assertThat(composer.getStatus().name()).isEqualTo(expected); }
    @Given("I gather signatures with the composer.")
    public void sign() throws Exception { composer.gatherSignatures(); }
    @Then("the base64 encoded signed transactions should equal {string}")
    public void golden(String expected) throws Exception {
        List<String> encoded = new ArrayList<>();
        for (SignedTransaction st : composer.gatherSignatures()) encoded.add(Encoder.encodeToBase64(Encoder.encodeToMsgPack(st)));
        assertThat(String.join(",", encoded)).isEqualTo(expected);
    }
    static class MethodCallStepsParams {
        int fee, first, last; byte[] hash; String id;
        MethodCallStepsParams(int f,int a,int b,byte[] h,String i){fee=f;first=a;last=b;hash=h;id=i;}
    }
}
