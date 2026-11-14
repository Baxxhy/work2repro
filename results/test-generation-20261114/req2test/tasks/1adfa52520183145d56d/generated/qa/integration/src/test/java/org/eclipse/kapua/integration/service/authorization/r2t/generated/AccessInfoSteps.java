package org.eclipse.kapua.integration.service.authorization.r2t.generated;

import com.google.inject.Singleton;
import io.cucumber.datatable.DataTable;
import io.cucumber.java.en.When;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.And;
import org.eclipse.kapua.locator.KapuaLocator;
import org.eclipse.kapua.model.id.KapuaId;
import org.eclipse.kapua.qa.common.StepData;
import org.eclipse.kapua.qa.common.cucumber.CucUser;
import org.eclipse.kapua.service.authentication.AuthenticationService;
import org.eclipse.kapua.service.authentication.UsernamePasswordCredentials;
import org.eclipse.kapua.service.authentication.CredentialsFactory;
import org.eclipse.kapua.service.authorization.access.AccessInfo;
import org.eclipse.kapua.service.authorization.access.AccessInfoCreator;
import org.eclipse.kapua.service.authorization.access.AccessInfoFactory;
import org.eclipse.kapua.service.authorization.access.AccessInfoService;
import org.eclipse.kapua.service.user.User;
import org.eclipse.kapua.service.user.UserCreator;
import org.eclipse.kapua.service.user.UserFactory;
import org.eclipse.kapua.service.user.UserService;
import org.eclipse.kapua.service.user.UserStatus;
import org.eclipse.kapua.service.user.UserType;
import org.eclipse.kapua.commons.configuration.KapuaConfigurableService;
import org.eclipse.kapua.service.user.UserService;
import org.junit.Assert;

import javax.inject.Inject;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;

@Singleton
public class AccessInfoSteps {
    private final StepData data;
    private final KapuaLocator locator = KapuaLocator.getInstance();
    private static final String ACCOUNT = "LastAccountId";
    private static final String USER = "LastUser";
    private static final String ACCESS = "LastAccessInfo";

    @Inject
    public AccessInfoSteps(StepData data) { this.data = data; }

    @When("I login as user with name {string} and password {string}")
    public void login(String name, String password) throws Exception {
        CredentialsFactory factory = locator.getService(CredentialsFactory.class);
        UsernamePasswordCredentials credentials = factory.newUsernamePasswordCredentials(name, password);
        locator.getService(AuthenticationService.class).login(credentials);
    }

    @When("I configure the user service for the account with the id {int}")
    public void configure(Integer id, DataTable table) throws Exception {
        Map<String, Object> values = new HashMap<>();
        for (Map<String, String> row : table.asMaps(String.class, String.class)) {
            String value = row.get("value");
            values.put(row.get("name"), "boolean".equals(row.get("type")) ? Boolean.valueOf(value) : Integer.valueOf(value));
        }
        locator.getService(UserService.class).setConfigValues(KapuaId.ONE, new org.eclipse.kapua.commons.model.id.KapuaEid(java.math.BigInteger.valueOf(id)), values);
    }

    @And("I have the following user")
    public void createUser(CucUser cuc) throws Exception {
        UserFactory factory = locator.getService(UserFactory.class);
        UserCreator creator = factory.newCreator((KapuaId) data.get(ACCOUNT), cuc.getName());
        creator.setDisplayName(cuc.getDisplayName());
        creator.setEmail(cuc.getEmail());
        creator.setPhoneNumber(cuc.getPhoneNumber());
        creator.setUserType(cuc.getUserType() == null ? UserType.INTERNAL : cuc.getUserType());
        creator.setStatus(cuc.getStatus() == null ? UserStatus.ENABLED : cuc.getStatus());
        User user = locator.getService(UserService.class).create(creator);
        data.put(USER, user);
    }

    @When("I create the access info entity")
    public void createAccessInfo() throws Exception {
        User user = (User) data.get(USER);
        AccessInfoCreator creator = locator.getService(AccessInfoFactory.class).newCreator(user.getScopeId());
        creator.setUserId(user.getId());
        creator.setPermissions(new HashSet<>());
        creator.setRoleIds(new HashSet<>());
        data.put(ACCESS, locator.getService(AccessInfoService.class).create(creator));
        data.put("ExceptionCaught", false);
    }

    @Then("An access info entity was created")
    public void created() { Assert.assertNotNull(data.get(ACCESS)); }

    @When("I search for the last created access info entity")
    public void find() throws Exception {
        AccessInfo created = (AccessInfo) data.get(ACCESS);
        data.put("FoundAccessInfo", locator.getService(AccessInfoService.class).find(created.getScopeId(), created.getId()));
    }

    @Then("I find an accessinfo entity")
    public void found() { Assert.assertNotNull(data.get("FoundAccessInfo")); }

    @Then("I logout")
    public void logout() throws Exception { locator.getService(AuthenticationService.class).logout(); }
}
