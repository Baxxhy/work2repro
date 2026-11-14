package org.eclipse.kapua.integration.service.authorization.r2t.generated;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import javax.inject.Inject;

import org.eclipse.kapua.commons.model.id.KapuaEid;
import org.eclipse.kapua.commons.util.RandomUtils;
import org.eclipse.kapua.locator.KapuaLocator;
import org.eclipse.kapua.qa.common.StepData;
import org.eclipse.kapua.qa.common.TestBase;
import org.eclipse.kapua.qa.common.cucumber.CucConfig;
import org.eclipse.kapua.qa.common.cucumber.CucGroup;
import org.eclipse.kapua.service.authentication.AuthenticationService;
import org.eclipse.kapua.service.authentication.CredentialsFactory;
import org.eclipse.kapua.service.authorization.group.Group;
import org.eclipse.kapua.service.authorization.group.GroupFactory;
import org.eclipse.kapua.service.authorization.group.GroupService;
import org.junit.Assert;

import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;
import io.cucumber.datatable.DataTable;

public class GroupFalseIdSteps extends TestBase {
    private final KapuaLocator locator = KapuaLocator.getInstance();
    private GroupService groupService;

    @Inject
    public GroupFalseIdSteps(StepData data) {
        super(data);
    }

    @When("I login as user with name {string} and password {string}")
    public void login(String username, String password) throws Exception {
        locator.getService(AuthenticationService.class).login(
                locator.getService(CredentialsFactory.class).newUsernamePasswordCredentials(username, password));
    }

    @When("I configure the group service")
    public void configureGroupService(List<CucConfig> configs) throws Exception {
        groupService = locator.getService(GroupService.class);
        Map<String, Object> values = new HashMap<>();
        for (CucConfig config : configs) {
            config.addConfigToMap(values);
        }
        groupService.setConfigValues(getKapuaId(0), getKapuaId(1), values);
    }

    @Given("I create the group")
    public void createGroup(List<CucGroup> groups) throws Exception {
        CucGroup data = groups.get(0);
        data.doParse();
        GroupFactory factory = locator.getFactory(GroupFactory.class);
        Group group = groupService.create(factory.newCreator(data.getScopeId(), data.getName()));
        stepData.put("Group", group);
    }

    @Then("A group was created")
    public void groupCreated() {
        Assert.assertNotNull(stepData.get("Group"));
    }

    @Then("The group matches the creator")
    public void groupMatchesCreator() {
        Group group = (Group) stepData.get("Group");
        Assert.assertEquals("test_name_4", group.getName());
        Assert.assertNotNull(group.getId());
        Assert.assertEquals(group.getScopeId(), group.getCreatedBy());
        Assert.assertNotNull(group.getCreatedOn());
    }

    @When("I update the group with an incorrect ID")
    public void updateGroupIncorrectId() throws Exception {
        Group group = (Group) stepData.get("Group");
        group.setId(new KapuaEid(RandomUtils.getInstance().nextLong() & Long.MAX_VALUE));
        try {
            groupService.update(group);
            stepData.put("ExceptionCaught", false);
        } catch (Exception ex) {
            verifyException(ex);
        }
    }

    @When("I logout")
    public void logout() {
        locator.getService(AuthenticationService.class).logout();
    }
}
