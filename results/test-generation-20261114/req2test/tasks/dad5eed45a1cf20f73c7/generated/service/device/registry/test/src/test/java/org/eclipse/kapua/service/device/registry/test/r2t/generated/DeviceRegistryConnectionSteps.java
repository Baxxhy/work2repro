package org.eclipse.kapua.service.device.registry.test.r2t.generated;

import com.google.inject.Singleton;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;
import org.eclipse.kapua.KapuaException;
import org.eclipse.kapua.locator.KapuaLocator;
import org.eclipse.kapua.model.id.KapuaId;
import org.eclipse.kapua.qa.common.StepData;
import org.eclipse.kapua.qa.common.TestBase;
import org.eclipse.kapua.qa.common.cucumber.CucConnection;
import org.eclipse.kapua.service.device.registry.connection.DeviceConnection;
import org.eclipse.kapua.service.device.registry.connection.DeviceConnectionCreator;
import org.eclipse.kapua.service.device.registry.connection.DeviceConnectionFactory;
import org.eclipse.kapua.service.device.registry.connection.DeviceConnectionService;
import org.junit.Assert;

import javax.inject.Inject;
import java.util.List;

@Singleton
public class DeviceRegistryConnectionSteps extends TestBase {
    private static final String CONNECTION_ID = "R2T_DEVICE_CONNECTION_ID";
    private static final String FOUND_CONNECTION = "R2T_FOUND_DEVICE_CONNECTION";

    @Inject
    public DeviceRegistryConnectionSteps(StepData stepData) {
        super(stepData);
    }

    @Given("I have the following connection")
    public void createConnection(CucConnection values) throws KapuaException {
        KapuaId scopeId = getCurrentScopeId();
        DeviceConnectionFactory factory = KapuaLocator.getInstance().getFactory(DeviceConnectionFactory.class);
        DeviceConnectionCreator creator = factory.newCreator(scopeId);
        creator.setClientId(values.getClientId());
        creator.setClientIp(values.getClientIp());
        creator.setServerIp(values.getServerIp());
        creator.setProtocol(values.getProtocol());
        creator.setAllowUserChange(values.getAllowUserChange());
        creator.setUserId(getCurrentUserId());

        DeviceConnection created = KapuaLocator.getInstance()
                .getService(DeviceConnectionService.class).create(creator);
        stepData.put(CONNECTION_ID, created.getId());
    }

    @When("I search for a connection by scope and connection IDs")
    public void findConnectionByIds() throws KapuaException {
        DeviceConnection found = KapuaLocator.getInstance().getService(DeviceConnectionService.class)
                .find(getCurrentScopeId(), (KapuaId) stepData.get(CONNECTION_ID));
        stepData.put(FOUND_CONNECTION, found);
    }

    @Then("The connection details match")
    public void assertConnectionDetails(List<CucConnection> expectedRows) {
        Assert.assertEquals("Expected exactly one connection row", 1, expectedRows.size());
        CucConnection expected = expectedRows.get(0);
        DeviceConnection actual = (DeviceConnection) stepData.get(FOUND_CONNECTION);
        Assert.assertNotNull("Connection was not found", actual);
        Assert.assertEquals(expected.getClientId(), actual.getClientId());
        Assert.assertEquals(expected.getClientIp(), actual.getClientIp());
        Assert.assertEquals(expected.getServerIp(), actual.getServerIp());
        Assert.assertEquals(expected.getProtocol(), actual.getProtocol());
        Assert.assertEquals(expected.getAllowUserChange(), actual.getAllowUserChange());
    }
}
