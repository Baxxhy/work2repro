package org.eclipse.kapua.service.tag.test.r2t.generated;

import java.util.HashSet;
import java.util.Set;
import javax.inject.Inject;

import com.google.inject.Singleton;
import org.eclipse.kapua.commons.model.query.QueryFactoryImpl;
import org.eclipse.kapua.locator.KapuaLocator;
import org.eclipse.kapua.model.id.KapuaId;
import org.eclipse.kapua.qa.common.StepData;
import org.eclipse.kapua.qa.common.TestBase;
import org.eclipse.kapua.service.device.registry.Device;
import org.eclipse.kapua.service.device.registry.DeviceCreator;
import org.eclipse.kapua.service.device.registry.DeviceFactory;
import org.eclipse.kapua.service.device.registry.DeviceRegistryService;
import org.eclipse.kapua.service.tag.Tag;
import org.eclipse.kapua.service.tag.TagCreator;
import org.eclipse.kapua.service.tag.TagFactory;
import org.eclipse.kapua.service.tag.TagService;
import org.junit.Assert;

import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;

@Singleton
public class TagServiceSteps extends TestBase {
    private static final String DEVICE = "r2t.device";
    private static final String TAG = "r2t.tag";

    @Inject
    public TagServiceSteps(StepData stepData) {
        super(stepData);
    }

    private DeviceFactory deviceFactory() {
        return KapuaLocator.getInstance().getService(DeviceFactory.class);
    }

    private DeviceRegistryService devices() {
        return KapuaLocator.getInstance().getService(DeviceRegistryService.class);
    }

    private TagFactory tagFactory() {
        return KapuaLocator.getInstance().getService(TagFactory.class);
    }

    private TagService tags() {
        return KapuaLocator.getInstance().getService(TagService.class);
    }

    @Given("A device named {string}")
    public void createDevice(String name) throws Exception {
        DeviceCreator creator = deviceFactory().newCreator(getCurrentScopeId(), name);
        creator.setClientId(name);
        stepData.put(DEVICE, devices().create(creator));
    }

    @Given("I create tag with name {string} without description")
    public void createTag(String name) throws Exception {
        TagCreator creator = tagFactory().newCreator(getCurrentScopeId(), name);
        stepData.put(TAG, tags().create(creator));
    }

    @When("I assign tag {string} to device {string}")
    public void assignTag(String tagName, String deviceName) throws Exception {
        Device device = (Device) stepData.get(DEVICE);
        Tag tag = (Tag) stepData.get(TAG);
        Assert.assertEquals(deviceName, device.getClientId());
        Assert.assertEquals(tagName, tag.getName());
        Set<KapuaId> ids = new HashSet<>(device.getTagIds() == null ? java.util.Collections.emptySet() : device.getTagIds());
        ids.add(tag.getId());
        device.setTagIds(ids);
        stepData.put(DEVICE, devices().update(device));
    }

    @Then("Tag {string} is assigned to device {string}")
    public void verifyAssignment(String tagName, String deviceName) throws Exception {
        Device device = (Device) stepData.get(DEVICE);
        Tag tag = (Tag) stepData.get(TAG);
        Assert.assertEquals(deviceName, device.getClientId());
        Assert.assertEquals(tagName, tag.getName());
        Device persisted = devices().find(getCurrentScopeId(), device.getId());
        Assert.assertNotNull(persisted);
        Assert.assertTrue(persisted.getTagIds().contains(tag.getId()));
        // Exercise the service query path as well, ensuring the created tag is persisted.
        org.eclipse.kapua.service.tag.TagQuery query = tagFactory().newQuery(getCurrentScopeId());
        query.setPredicate(query.attributePredicate("name", tagName,
                org.eclipse.kapua.model.query.predicate.AttributePredicate.Operator.EQUAL));
        Assert.assertEquals(tag.getId(), tags().query(query).getFirstItem().getId());
    }
}
