package com.algorand.algosdk.unit;

import com.algorand.algosdk.crypto.Address;
import com.algorand.algosdk.util.Encoder;
import com.algorand.algosdk.v2.client.common.IndexerClient;
import com.algorand.algosdk.v2.client.indexer.LookupAccountTransactions;
import com.algorand.algosdk.v2.client.model.Enums;
import com.algorand.algosdk.v2.client.common.Utils;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;

import static org.assertj.core.api.Assertions.assertThat;

public class IndexerClientV2PathsSteps {
    private String actualPath;

    @Given("mock server recording request paths")
    public void mockServerRecordingRequestPaths() {
        // The query URL is deterministic and can be checked without issuing a network call.
    }

    @When("we make a Lookup Account Transactions call against account {string} with NotePrefix {string} TxType {string} SigType {string} txid {string} round {long} minRound {long} maxRound {long} limit {long} beforeTime {string} afterTime {string} currencyGreaterThan {long} currencyLessThan {long} assetIndex {long}")
    public void lookupAccountTransactions(String account, String notePrefixB64, String txType, String sigType,
            String txid, long round, long minRound, long maxRound, long limit, String beforeTime, String afterTime,
            long currencyGreaterThan, long currencyLessThan, long index) throws Exception {
        IndexerClient client = new IndexerClient("http://localhost", 8980, "");
        LookupAccountTransactions query = client.lookupAccountTransactions(new Address(account));
        if (!notePrefixB64.isEmpty()) query.notePrefix(Encoder.decodeFromBase64(notePrefixB64));
        if (!txType.isEmpty()) query.txType(Enums.TxType.forValue(txType));
        if (!sigType.isEmpty()) query.sigType(Enums.SigType.forValue(sigType));
        if (!txid.isEmpty()) query.txid(txid);
        if (round != 0) query.round(round);
        if (minRound != 0) query.minRound(minRound);
        if (maxRound != 0) query.maxRound(maxRound);
        if (limit != 0) query.limit(limit);
        if (!beforeTime.isEmpty()) query.beforeTime(Utils.parseDate(beforeTime));
        if (!afterTime.isEmpty()) query.afterTime(Utils.parseDate(afterTime));
        query.currencyGreaterThan(currencyGreaterThan);
        if (currencyLessThan != 0) query.currencyLessThan(currencyLessThan);
        if (index != 0) query.assetId(index);
        String url = query.getRequestUrl();
        int start = url.indexOf("/v2/");
        actualPath = start >= 0 ? url.substring(start) : url;
    }

    @Then("expect the path used to be {string}")
    public void expectPath(String expectedPath) {
        assertThat(actualPath).isEqualTo(expectedPath);
    }
}
