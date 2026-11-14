package org.eclipse.kapua.service.user.test.r2t.generated;

import com.google.inject.Singleton;
import io.cucumber.datatable.DataTable;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;
import org.eclipse.kapua.commons.configuration.KapuaConfigurableServiceBase;
import org.eclipse.kapua.locator.KapuaLocator;
import org.eclipse.kapua.model.id.KapuaId;
import org.eclipse.kapua.commons.model.id.KapuaEid;
import org.eclipse.kapua.qa.common.cucumber.CucConfig;
import org.eclipse.kapua.qa.common.cucumber.CucUser;
import org.eclipse.kapua.service.user.User;
import org.eclipse.kapua.service.user.UserCreator;
import org.eclipse.kapua.service.user.UserFactory;
import org.eclipse.kapua.service.user.UserService;
import org.junit.Assert;

import javax.inject.Inject;
import java.math.BigInteger;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Singleton
public class UserSteps {
    private final UserService userService;
    private final UserFactory userFactory;
    private User createdUser;
    private User foundUser;

    @Inject
    public UserSteps() {
        KapuaLocator locator = KapuaLocator.getInstance();
        userService = locator.getService(UserService.class);
        userFactory = locator.getFactory(UserFactory.class);
    }

    @When("I configure the user service for the account with the id {int}")
    public void configureUserService(int accountId, DataTable table) throws Exception {
        Map<String, Object> values = new HashMap<>();
        List<CucConfig> configs = table.asList(CucConfig.class);
        for (CucConfig config : configs) {
            config.addConfigToMap(values);
        }
        KapuaId id = new KapuaEid(BigInteger.valueOf(accountId));
        ((KapuaConfigurableServiceBase) userService).setConfigValues(id, null, values);
    }

    @Given("I have the following user")
    public void createUser(DataTable table) throws Exception {
        CucUser data = table.asList(CucUser.class).get(0);
        KapuaId scopeId = new KapuaEid(BigInteger.valueOf(42));
        UserCreator creator = userFactory.newCreator(scopeId, data.getName());
        creator.setDisplayName(data.getDisplayName());
        creator.setEmail(data.getEmail());
        creator.setPhoneNumber(data.getPhoneNumber());
        creator.setStatus(data.getStatus());
        createdUser = userService.create(creator);
    }

    @When("I search for user with name {string}")
    public void findUserByName(String name) throws Exception {
        foundUser = userService.findByName(name);
    }

    @Then("I find user")
    public void verifyUser(DataTable table) {
        List<String> row = table.cells().get(0);
        Assert.assertNotNull("User should be found", foundUser);
        Assert.assertEquals(row.get(0), foundUser.getName());
        Assert.assertEquals(row.get(1), foundUser.getDisplayName());
        Assert.assertEquals(row.get(2), foundUser.getEmail());
        Assert.assertEquals(row.get(3), foundUser.getPhoneNumber());
        Assert.assertEquals(row.get(4), foundUser.getStatus().name());
        Assert.assertNotNull(createdUser);
        Assert.assertEquals(createdUser.getId(), foundUser.getId());
    }
}
