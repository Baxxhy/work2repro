package org.eclipse.kapua.service.device.registry.test.r2t.generated;

import com.google.inject.Singleton;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.datatable.DataTable;
import org.eclipse.kapua.locator.KapuaLocator;
import org.eclipse.kapua.model.id.KapuaId;
import org.eclipse.kapua.qa.common.StepData;
import org.eclipse.kapua.service.device.registry.connection.DeviceConnection;
import org.eclipse.kapua.service.device.registry.connection.DeviceConnectionCreator;
import org.eclipse.kapua.service.device.registry.connection.DeviceConnectionFactory;
import org.eclipse.kapua.service.device.registry.connection.DeviceConnectionService;
import org.junit.Assert;

import javax.inject.Inject;
import java.util.Map;

@Singleton
public class RegularConnectionSteps {
    private static final String SCOPE = "LastAccountId";
    private static final String USER = "LastUserId";
    private static final String CONNECTION = "RegularDeviceConnection";

    private final StepData data;

    @Inject
    public RegularConnectionSteps(StepData data) {
        this.data = data;
    }

    @Given("I have the following connection")
    public void createConnection(DataTable table) throws Exception {
        Map<String, String> row = table.asMaps(String.class, String.class).get(0);
        KapuaId scopeId = (KapuaId) data.get(SCOPE);
        DeviceConnectionFactory factory = KapuaLocator.getInstance().getFactory(DeviceConnectionFactory.class);
        DeviceConnectionCreator creator = factory.newCreator(scopeId);
        creator.setClientId(row.get("clientId"));
        creator.setUserId((KapuaId) data.get(USER));
        creator.setClientIp(row.get("clientIp"));
        creator.setServerIp(row.get("serverIp"));
        creator.setProtocol(row.get("protocol"));
        creator.setAllowUserChange(Boolean.parseBoolean(row.get("allowUserChange")));
        DeviceConnection connection = KapuaLocator.getInstance().getService(DeviceConnectionService.class).create(creator);
        data.put(CONNECTION, connection);
    }

    @Then("The connection object is regular")
    public void connectionIsRegular() {
        DeviceConnection connection = connection();
        Assert.assertNotNull(connection);
        Assert.assertNotNull(connection.getId());
    }

    @Then("The connection details match")
    public void connectionDetailsMatch(DataTable table) {
        DeviceConnection connection = connection();
        Map<String, String> row = table.asMaps(String.class, String.class).get(0);
        Assert.assertEquals(row.get("clientId"), connection.getClientId());
        Assert.assertEquals(row.get("clientIp"), connection.getClientIp());
        Assert.assertEquals(row.get("serverIp"), connection.getServerIp());
        Assert.assertEquals(row.get("protocol"), connection.getProtocol());
        Assert.assertEquals(Boolean.parseBoolean(row.get("allowUserChange")), connection.getAllowUserChange());
    }

    @Then("The connection status is {string}")
    public void connectionStatusIs(String status) {
        Assert.assertEquals(status, connection().getStatus().name());
    }

    private DeviceConnection connection() {
        return (DeviceConnection) data.get(CONNECTION);
    }
}
