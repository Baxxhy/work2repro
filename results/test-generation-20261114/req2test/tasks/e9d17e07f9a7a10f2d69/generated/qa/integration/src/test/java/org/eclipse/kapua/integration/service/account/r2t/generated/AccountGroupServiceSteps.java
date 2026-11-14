package org.eclipse.kapua.integration.service.account.r2t.generated;

import java.util.HashMap;
import java.util.Map;

import javax.inject.Inject;

import com.google.inject.Singleton;
import org.eclipse.kapua.locator.KapuaLocator;
import org.eclipse.kapua.model.id.KapuaId;
import org.eclipse.kapua.qa.common.StepData;
import org.eclipse.kapua.qa.common.TestBase;
import org.eclipse.kapua.qa.common.cucumber.CucConfig;
import org.eclipse.kapua.service.account.Account;
import org.eclipse.kapua.service.account.AccountCreator;
import org.eclipse.kapua.service.account.AccountFactory;
import org.eclipse.kapua.service.account.AccountService;
import org.eclipse.kapua.service.authentication.AuthenticationService;
import org.eclipse.kapua.service.authentication.CredentialsFactory;
import org.eclipse.kapua.service.authorization.group.GroupCreator;
import org.eclipse.kapua.service.authorization.group.GroupFactory;
import org.eclipse.kapua.service.authorization.group.GroupService;
import io.cucumber.datatable.DataTable;
import io.cucumber.java.en.And;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;

@Singleton
public class AccountGroupServiceSteps extends TestBase {
    private static final String ACCOUNT_KEY = "GeneratedAccount";
    private static final String SELECTED_SCOPE_KEY = "LastAccountId";

    @Inject
    public AccountGroupServiceSteps(StepData stepData) {
        super(stepData);
    }

    @Given("I login as user with name {string} and password {string}")
    public void login(String username, String password) throws Exception {
        CredentialsFactory factory = KapuaLocator.getInstance().getFactory(CredentialsFactory.class);
        KapuaLocator.getInstance().getService(AuthenticationService.class)
                .login(factory.newUsernamePasswordCredentials(username, password));
    }

    @Then("I create an account with name {string}, organization name {string} and email address {string}")
    public void createAccount(String name, String organization, String email) throws Exception {
        AccountFactory factory = KapuaLocator.getInstance().getFactory(AccountFactory.class);
        AccountCreator creator = factory.newCreator(KapuaId.ONE);
        creator.setName(name);
        creator.setOrganizationName(organization);
        creator.setOrganizationEmail(email);
        Account account = KapuaLocator.getInstance().getService(AccountService.class).create(creator);
        stepData.put(ACCOUNT_KEY, account);
        stepData.put(SELECTED_SCOPE_KEY, account.getId());
    }

    @And("I configure the group service")
    public void configureGroupService(DataTable table) throws Exception {
        Account account = (Account) stepData.get(ACCOUNT_KEY);
        Map<String, Object> values = new HashMap<>();
        for (CucConfig config : table.asList(CucConfig.class)) {
            config.addConfigToMap(values);
        }
        KapuaId scopeId = account.getId();
        KapuaLocator.getInstance().getService(GroupService.class)
                .setConfigValues(scopeId, account.getScopeId(), values);
    }

    @Then("I select account {string}")
    public void selectAccount(String name) throws Exception {
        Account account = KapuaLocator.getInstance().getService(AccountService.class).findByName(name);
        stepData.put(ACCOUNT_KEY, account);
        stepData.put(SELECTED_SCOPE_KEY, account.getId());
    }

    @And("I create a group with name {string}")
    public void createGroup(String name) throws Exception {
        KapuaId scopeId = (KapuaId) stepData.get(SELECTED_SCOPE_KEY);
        GroupFactory factory = KapuaLocator.getInstance().getFactory(GroupFactory.class);
        GroupCreator creator = factory.newCreator(scopeId);
        creator.setName(name);
        KapuaLocator.getInstance().getService(GroupService.class).create(creator);
    }

    @And("I logout")
    public void logout() throws Exception {
        KapuaLocator.getInstance().getService(AuthenticationService.class).logout();
    }
}
