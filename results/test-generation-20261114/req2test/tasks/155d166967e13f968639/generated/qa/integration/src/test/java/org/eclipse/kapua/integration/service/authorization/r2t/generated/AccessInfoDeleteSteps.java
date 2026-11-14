package org.eclipse.kapua.integration.service.authorization.r2t.generated;

import com.google.inject.Singleton;
import io.cucumber.datatable.DataTable;
import io.cucumber.java.en.When;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.And;
import org.eclipse.kapua.locator.KapuaLocator;
import org.eclipse.kapua.model.id.KapuaId;
import org.eclipse.kapua.qa.common.StepData;
import org.eclipse.kapua.service.authorization.access.*;
import org.eclipse.kapua.service.authorization.domain.*;
import org.eclipse.kapua.service.authorization.permission.*;
import org.eclipse.kapua.service.authorization.role.*;
import org.eclipse.kapua.service.authentication.*;
import org.eclipse.kapua.service.authentication.token.AccessToken;
import org.eclipse.kapua.service.user.*;
import org.eclipse.kapua.commons.configuration.KapuaConfigurableService;
import org.junit.Assert;

import javax.inject.Inject;
import java.util.*;

@Singleton
public class AccessInfoDeleteSteps {
    private static final String ACCOUNT = "LastAccountId";
    private static final String USER = "LastUserId";
    private static final String ACCESS_INFO = "R2TAccessInfo";
    private static final String ACCESS_ROLE = "R2TAccessRole";
    private static final String PERMISSIONS = "R2TPermissions";
    private static final String ROLE = "R2TRole";
    private final StepData data;

    @Inject public AccessInfoDeleteSteps(StepData data) { this.data = data; }

    private KapuaId account() { return (KapuaId) data.get(ACCOUNT); }

    @When("I login as user with name {string} and password {string}")
    public void login(String name, String password) throws Exception {
        AuthenticationService auth = KapuaLocator.getInstance().getService(AuthenticationService.class);
        CredentialsFactory factory = KapuaLocator.getInstance().getFactory(CredentialsFactory.class);
        auth.login(factory.newUsernamePasswordCredentials(name, password));
    }

    @When("I configure the user service for the account with the id {int}")
    public void configure(int id, DataTable table) throws Exception {
        Map<String, Object> config = new HashMap<>();
        for (List<String> row : table.asLists()) {
            if (row.size() == 3 && !"type".equals(row.get(0))) {
                Object value = "boolean".equals(row.get(0)) ? Boolean.valueOf(row.get(2)) :
                        "integer".equals(row.get(0)) ? Integer.valueOf(row.get(2)) : row.get(2);
                config.put(row.get(1), value);
            }
        }
        ((KapuaConfigurableService) KapuaLocator.getInstance().getService(UserService.class))
                .setConfigValues(account(), null, config);
    }

    @When("I create the domain")
    public void createDomain(DataTable table) throws Exception {
        List<String> row = table.asLists().get(1);
        Set<Actions> actions = new HashSet<>();
        for (String s : row.get(1).split(",")) actions.add(Actions.valueOf(s.trim().toUpperCase()));
        DomainCreator creator = KapuaLocator.getInstance().getFactory(DomainFactory.class).newCreator(row.get(0));
        creator.setActions(actions);
        creator.setServiceName(row.get(0));
        KapuaLocator.getInstance().getService(DomainRegistryService.class).create(creator);
    }

    @When("I have the following user")
    public void createUser(DataTable table) throws Exception {
        List<String> row = table.asLists().get(1);
        UserCreator c = KapuaLocator.getInstance().getFactory(UserFactory.class).newCreator(account(), row.get(0));
        c.setDisplayName(row.get(1)); c.setEmail(row.get(2)); c.setPhoneNumber(row.get(3));
        data.put(USER, KapuaLocator.getInstance().getService(UserService.class).create(c).getId());
    }

    @When("I create the access info entity")
    public void createAccessInfo() throws Exception {
        AccessInfoCreator c = KapuaLocator.getInstance().getFactory(AccessInfoFactory.class).newCreator(account());
        c.setUserId((KapuaId) data.get(USER));
        c.setPermissions(Collections.emptySet()); c.setRoleIds(Collections.emptySet());
        data.put(ACCESS_INFO, KapuaLocator.getInstance().getService(AccessInfoService.class).create(c).getId());
    }

    @And("The permissions {string}")
    public void permissions(String text) throws Exception {
        Set<Permission> set = new HashSet<>();
        for (String action : text.split(",")) set.add(KapuaLocator.getInstance().getFactory(PermissionFactory.class)
                .newPermission("test", Actions.valueOf(action.trim().toUpperCase()), account()));
        data.put(PERMISSIONS, set);
    }

    @And("The role {string}")
    public void role(String name) throws Exception {
        RoleCreator c = KapuaLocator.getInstance().getFactory(RoleFactory.class).newCreator(account());
        c.setName(name); c.setPermissions((Set<Permission>) data.get(PERMISSIONS));
        data.put(ROLE, KapuaLocator.getInstance().getService(RoleService.class).create(c).getId());
    }

    @When("I create the access role")
    public void createAccessRole() throws Exception {
        AccessRoleCreator c = KapuaLocator.getInstance().getFactory(AccessRoleFactory.class).newCreator(account());
        c.setAccessInfoId((KapuaId) data.get(ACCESS_INFO)); c.setRoleId((KapuaId) data.get(ROLE));
        data.put(ACCESS_ROLE, KapuaLocator.getInstance().getService(AccessRoleService.class).create(c).getId());
    }

    @When("I count the access roles in scope {int}")
    public void countRoles(int id) throws Exception {
        AccessRoleService service = KapuaLocator.getInstance().getService(AccessRoleService.class);
        data.updateCount(service.count(account()));
    }

    @Then("I count {int}")
    public void assertCount(int count) { Assert.assertEquals(count, data.getCount()); }

    @When("I delete the last created access role entry")
    public void deleteRole() throws Exception {
        KapuaLocator.getInstance().getService(AccessRoleService.class).delete(account(), (KapuaId) data.get(ACCESS_ROLE));
    }

    @Then("I logout")
    public void logout() throws Exception { KapuaLocator.getInstance().getService(AuthenticationService.class).logout(); }
}
