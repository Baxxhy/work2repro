package com.algorand.algosdk.unit;

import com.algorand.algosdk.v2.client.algod.GetApplicationBoxByName;
import com.algorand.algosdk.v2.client.common.AlgodClient;
import com.sun.net.httpserver.HttpServer;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.When;
import io.cucumber.java.en.Then;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;

import static org.assertj.core.api.Assertions.assertThat;

public class AlgodRestApiV2PathsSteps {
    private HttpServer server;
    private String recordedPath;
    private AlgodClient client;

    @Given("mock server recording request paths")
    public void mockServerRecordingRequestPaths() throws IOException {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/", exchange -> {
            recordedPath = exchange.getRequestURI().toASCIIString();
            byte[] body = "{}".getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(404, body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
        });
        server.start();
        client = new AlgodClient("http://127.0.0.1", server.getAddress().getPort(), "");
    }

    @When("we make a GetApplicationBoxByName call for applicationID {long} with encoded box name {string}")
    public void makeGetApplicationBoxByNameCall(long applicationId, String encodedBoxName) throws Exception {
        GetApplicationBoxByName query = client.GetApplicationBoxByName(applicationId).name(encodedBoxName);
        try {
            query.execute();
        } catch (Exception ignored) {
            // The test server intentionally returns 404; the request itself is what is under test.
        }
    }

    @Then("expect the path used to be {string}")
    public void expectPathUsedToBe(String expectedPath) {
        assertThat(recordedPath).isEqualTo(expectedPath);
        server.stop(0);
    }
}
