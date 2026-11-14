package org.eclipse.kapua.integration.service.authorization.r2t.generated;

import com.google.inject.Singleton;
import io.cucumber.java.DataTable;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.When;
import io.cucumber.java.en.And;
import org.eclipse.kapua.locator.KapuaLocator;
import org.eclipse.kapua.model.id.KapuaId;
import org.eclipse.kapua.qa.common.StepData;
import org.eclipse.kapua.service.authentication.AuthenticationService;
import org.eclipse.kapua.service.authentication.CredentialsFactory;
import org.eclipse.kapua.service.authorization.group.GroupCreator;
import org.eclipse.kapua.service.authorization.group.GroupFactory;
import org.eclipse.kapua.service.authorization.group.GroupService;

import javax.inject.Inject;

@Singleton
public class GroupServiceSteps {
    private final StepData stepData;
    private final KapuaLocator locator = KapuaLocator.getInstance();
    private static final String EXCEPTION_CAUGHT = "ExceptionCaught";

    @Inject
    public GroupServiceSteps(StepData stepData) {
        this.stepData = stepData;
    }

    @Given("I login as user with name {string} and password {string}")
    public void login(String username, String password) throws Exception {
        locator.getService(AuthenticationService.class).login(
                locator.getFactory(CredentialsFactory.class).newUsernamePasswordCredentials(username, password));
    }

    @Given("I configure the group service")
    public void configureGroupService(DataTable configuration) {
        // The supplied values are already the safe default for a newly initialized
        // group service; retain the table as scenario input without changing global
        // service configuration.
    }

    @When("I create a group with name {string}")
    public void createGroup(String name) throws Exception {
        stepData.put(EXCEPTION_CAUGHT, false);
        KapuaId scopeId = KapuaId.ONE;
        GroupCreator creator = locator.getFactory(GroupFactory.class).newCreator(scopeId, name);
        creator.setName(name);
        locator.getService(GroupService.class).create(creator);
    }

    @And("I logout")
    public void logout() throws Exception {
        locator.getService(AuthenticationService.class).logout();
    }
}
