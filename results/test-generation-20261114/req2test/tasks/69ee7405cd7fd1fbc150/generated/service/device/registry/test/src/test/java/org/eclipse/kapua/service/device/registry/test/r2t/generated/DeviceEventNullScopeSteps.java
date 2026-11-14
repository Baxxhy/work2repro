package org.eclipse.kapua.service.device.registry.test.r2t.generated;

import java.util.Date;
import java.util.HashMap;
import java.util.Map;

import javax.inject.Inject;

import com.google.inject.Singleton;
import org.eclipse.kapua.KapuaException;
import org.eclipse.kapua.locator.KapuaLocator;
import org.eclipse.kapua.model.id.KapuaId;
import org.eclipse.kapua.qa.common.StepData;
import org.eclipse.kapua.qa.common.TestBase;
import org.eclipse.kapua.service.device.management.message.KapuaMethod;
import org.eclipse.kapua.service.device.registry.Device;
import org.eclipse.kapua.service.device.registry.DeviceCreator;
import org.eclipse.kapua.service.device.registry.DeviceFactory;
import org.eclipse.kapua.service.device.registry.DeviceRegistryService;
import org.eclipse.kapua.service.device.registry.event.DeviceEventCreator;
import org.eclipse.kapua.service.device.registry.event.DeviceEventFactory;
import org.eclipse.kapua.service.device.registry.event.DeviceEventService;

import io.cucumber.java.en.Given;
import io.cucumber.java.en.When;

@Singleton
public class DeviceEventNullScopeSteps extends TestBase {
    private static final String DEVICES = "R2TDeviceEvents";
    private final Map<String, KapuaId> devices = new HashMap<>();

    @Inject
    public DeviceEventNullScopeSteps(StepData stepData) {
        super(stepData);
    }

    @Given("A device named {string}")
    public void createDevice(String name) throws Exception {
        KapuaId scopeId = getCurrentScopeId();
        DeviceFactory factory = KapuaLocator.getInstance().getFactory(DeviceFactory.class);
        DeviceCreator creator = factory.newCreator(scopeId);
        creator.setClientId(name);
        try {
            Device device = KapuaLocator.getInstance().getService(DeviceRegistryService.class).create(scopeId, creator);
            devices.put(name, device.getId());
        } catch (Exception e) {
            verifyException(e);
        }
    }

    @When("A {string} event from device {string}")
    public void createEvent(String action, String deviceName) throws Exception {
        primeException();
        try {
            DeviceEventFactory factory = KapuaLocator.getInstance().getFactory(DeviceEventFactory.class);
            DeviceEventCreator creator = factory.newCreator(getCurrentScopeId());
            creator.setDeviceId(devices.get(deviceName));
            creator.setAction(KapuaMethod.valueOf(action));
            creator.setReceivedOn(new Date());
            KapuaLocator.getInstance().getService(DeviceEventService.class).create(creator);
        } catch (Exception e) {
            verifyException(e);
        }
    }
}
