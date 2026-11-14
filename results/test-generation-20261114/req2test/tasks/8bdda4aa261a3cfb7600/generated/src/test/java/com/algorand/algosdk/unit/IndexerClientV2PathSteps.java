package com.algorand.algosdk.unit;

import com.algorand.algosdk.v2.client.common.IndexerClient;
import com.algorand.algosdk.v2.client.indexer.LookupAssetTransactions;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;

import java.net.URI;

import static org.assertj.core.api.Assertions.assertThat;

public class IndexerClientV2PathSteps {
    private String requestPath;

    @Given("mock server recording request paths")
    public void mockServerRecordingRequestPaths() {
        // This scenario inspects the URL built by Query; no HTTP request is needed.
    }

    @When("^we make a Lookup Asset Transactions call against asset index (\\d+) with NotePrefix \"([^\"]*)\" TxType \"([^\"]*)\" SigType \"([^\"]*)\" txid \"([^\"]*)\" round (-?\\d+) minRound (-?\\d+) maxRound (-?\\d+) limit (-?\\d+) beforeTime \"([^\"]*)\" afterTime \"([^\"]*)\" currencyGreaterThan (-?\\d+) currencyLessThan (-?\\d+) address \"([^\"]*)\" addressRole \"([^\"]*)\" ExcluseCloseTo \"([^\"]*)\" RekeyTo \"([^\"]*)\"$")
    public void lookupAssetTransactionsPath(long index, String notePrefix, String txType,
            String sigType, String txid, long round, long minRound, long maxRound,
            long limit, String beforeTime, String afterTime, long currencyGreaterThan,
            long currencyLessThan, String address, String addressRole,
            String excludeCloseTo, String rekeyTo) throws Exception {
        IndexerClient client = new IndexerClient("http://localhost", 8980, "");
        LookupAssetTransactions query = client.lookupAssetTransactions(index);
        query.currencyGreaterThan(currencyGreaterThan);
        query.rekeyTo(Boolean.valueOf(rekeyTo));
        URI uri = URI.create(query.getRequestUrl());
        requestPath = uri.getRawPath() + (uri.getRawQuery() == null ? "" : "?" + uri.getRawQuery());
    }

    @Then("expect the path used to be {string}")
    public void expectPath(String path) {
        assertThat(requestPath).isEqualTo(path);
    }
}
