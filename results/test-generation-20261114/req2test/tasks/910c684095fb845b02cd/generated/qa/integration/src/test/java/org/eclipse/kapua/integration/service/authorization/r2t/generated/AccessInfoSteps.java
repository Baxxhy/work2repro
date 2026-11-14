package org.eclipse.kapua.integration.service.authorization.r2t.generated;

import com.google.inject.Singleton;
import io.cucumber.datatable.DataTable;
import io.cucumber.java.en.*;
import java.math.BigInteger;
import java.util.*;
import javax.inject.Inject;
import org.eclipse.kapua.commons.model.id.KapuaEid;
import org.eclipse.kapua.commons.configuration.KapuaConfigurableService;
import org.eclipse.kapua.locator.KapuaLocator;
import org.eclipse.kapua.model.domain.Actions;
import org.eclipse.kapua.model.id.KapuaId;
import org.eclipse.kapua.qa.common.StepData;
import org.eclipse.kapua.service.authentication.*;
import org.eclipse.kapua.service.authorization.access.*;
import org.eclipse.kapua.service.authorization.domain.*;
import org.eclipse.kapua.service.authorization.permission.PermissionFactory;
import org.eclipse.kapua.service.user.*;
import org.junit.Assert;

@Singleton
public class AccessInfoSteps {
    private final StepData data;
    private KapuaId scope = new KapuaEid(BigInteger.TEN);
    private AccessInfo accessInfo;
    private AccessPermission lastPermission;
    private List<Actions> actions = new ArrayList<>();

    @Inject public AccessInfoSteps(StepData data) { this.data = data; }

    @When("I login as user with name {string} and password {string}")
    public void login(String name, String password) throws Exception {
        KapuaLocator.getInstance().getService(AuthenticationService.class)
            .login(KapuaLocator.getInstance().getService(CredentialsFactory.class).newUsernamePasswordCredentials(name, password));
    }

    @Given("Scope with ID {int}")
    public void scope(int id) { scope = new KapuaEid(BigInteger.valueOf(id)); }

    @When("I configure the user service for the account with the id {int}")
    public void configure(int id, DataTable table) throws Exception {
        Map<String,Object> values = new HashMap<>();
        for (Map<String,String> row : table.asMaps()) {
            String type=row.get("type"), value=row.get("value");
            values.put(row.get("name"), "boolean".equals(type) ? Boolean.valueOf(value) : Integer.valueOf(value));
        }
        KapuaLocator.getInstance().getService(UserService.class).setConfigValues(scope, scope, values);
    }

    @And("I have the following user")
    public void createUser(DataTable table) throws Exception {
        Map<String,String> row=table.asMaps().get(0);
        UserCreator c=KapuaLocator.getInstance().getService(UserFactory.class).newCreator(scope,row.get("name"));
        c.setDisplayName(row.get("displayName")); c.setEmail(row.get("email")); c.setPhoneNumber(row.get("phoneNumber"));
        User u=KapuaLocator.getInstance().getService(UserService.class).create(c);
        data.put("accessUser",u);
    }

    @And("I create the domain")
    public void createDomain(DataTable table) throws Exception {
        Map<String,String> row=table.asMaps().get(0);
        DomainCreator c=KapuaLocator.getInstance().getService(DomainFactory.class).newCreator(row.get("name"));
        c.setServiceName("test");
        Set<Actions> set=new HashSet<>();
        for(String a:row.get("actions").split(",")) set.add(Actions.valueOf(a.trim()));
        c.setActions(set);
        KapuaLocator.getInstance().getService(DomainRegistryService.class).create(c);
    }

    @When("I create the access info entity")
    public void createAccessInfo() throws Exception {
        AccessInfoCreator c=KapuaLocator.getInstance().getService(AccessInfoFactory.class).newCreator(scope);
        c.setUserId(((User)data.get("accessUser")).getId());
        c.setRoleIds(Collections.emptySet()); c.setPermissions(Collections.emptySet());
        accessInfo=KapuaLocator.getInstance().getService(AccessInfoService.class).create(c);
    }

    @And("The permissions {string}")
    public void permissionActions(String text) {
        for(String s:text.split(",")) actions.add(Actions.valueOf(s.trim()));
    }

    @And("I create the permissions")
    public void createPermissions() throws Exception {
        for(Actions action:actions) {
            org.eclipse.kapua.service.authorization.permission.Permission p =
                KapuaLocator.getInstance().getService(PermissionFactory.class).newPermission("test", action, scope);
            AccessPermissionCreator c=KapuaLocator.getInstance().getService(AccessPermissionFactory.class).newCreator(scope);
            c.setAccessInfoId(accessInfo.getId()); c.setPermission(p);
            lastPermission=KapuaLocator.getInstance().getService(AccessPermissionService.class).create(c);
        }
    }

    @When("I count the permissions in scope {int}")
    public void count(int id) throws Exception {
        AccessPermissionQuery q=KapuaLocator.getInstance().getService(AccessPermissionFactory.class).newQuery(new KapuaEid(BigInteger.valueOf(id)));
        data.updateCount((int)KapuaLocator.getInstance().getService(AccessPermissionService.class).count(q));
    }
    @Then("I count {int}")
    public void checkCount(int n) { Assert.assertEquals(n,data.getCount()); }
    @When("I delete the last created access permission")
    public void delete() throws Exception {
        KapuaLocator.getInstance().getService(AccessPermissionService.class).delete(lastPermission.getScopeId(),lastPermission.getId());
    }
    @Then("I logout")
    public void logout() throws Exception { KapuaLocator.getInstance().getService(AuthenticationService.class).logout(); }
}
