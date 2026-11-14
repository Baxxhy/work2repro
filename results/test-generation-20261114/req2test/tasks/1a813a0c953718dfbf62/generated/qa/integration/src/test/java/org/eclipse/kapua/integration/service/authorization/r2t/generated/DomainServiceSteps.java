package org.eclipse.kapua.integration.service.authorization.r2t.generated;

import javax.inject.Inject;

import org.eclipse.kapua.commons.security.KapuaSecurityUtils;
import org.eclipse.kapua.locator.KapuaLocator;
import org.eclipse.kapua.model.domain.Actions;
import org.eclipse.kapua.model.id.KapuaId;
import org.eclipse.kapua.qa.common.StepData;
import org.eclipse.kapua.qa.common.cucumber.CucDomain;
import org.eclipse.kapua.service.authentication.AuthenticationService;
import org.eclipse.kapua.service.authentication.CredentialsFactory;
import org.eclipse.kapua.service.authorization.domain.Domain;
import org.eclipse.kapua.service.authorization.domain.DomainCreator;
import org.eclipse.kapua.service.authorization.domain.DomainFactory;
import org.eclipse.kapua.service.authorization.domain.DomainRegistryService;
import org.junit.Assert;

import com.google.inject.Singleton;

import io.cucumber.datatable.DataTable;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;

@Singleton
public class DomainServiceSteps {
    private static final String CREATOR = "LastDomainCreator";
    private static final String DOMAIN = "LastDomain";

    private final StepData stepData;

    @Inject
    public DomainServiceSteps(StepData stepData) {
        this.stepData = stepData;
    }

    @When("I login as user with name {string} and password {string}")
    public void login(String username, String password) throws Exception {
        KapuaLocator locator = KapuaLocator.getInstance();
        locator.getService(AuthenticationService.class)
                .login(locator.getFactory(CredentialsFactory.class)
                        .newUsernamePasswordCredentials(username, password));
    }

    @Given("I create the domain")
    public void createDomain(DataTable table) throws Exception {
        CucDomain values = table.asList(CucDomain.class).get(0);
        values.doParse();
        DomainCreator creator = KapuaLocator.getInstance().getFactory(DomainFactory.class)
                .newCreator(values.getName());
        creator.setActions(values.getActionSet());
        Domain created = KapuaLocator.getInstance().getService(DomainRegistryService.class).create(creator);
        stepData.put(CREATOR, creator);
        stepData.put(DOMAIN, created);
    }

    @When("I search for the last created domain")
    public void findLastDomain() throws Exception {
        Domain created = (Domain) stepData.get(DOMAIN);
        KapuaId scopeId = KapuaSecurityUtils.getSession().getScopeId();
        stepData.put(DOMAIN, KapuaLocator.getInstance().getService(DomainRegistryService.class)
                .find(scopeId, created.getId()));
    }

    @Then("The domain matches the creator")
    public void domainMatchesCreator() {
        Domain domain = (Domain) stepData.get(DOMAIN);
        DomainCreator creator = (DomainCreator) stepData.get(CREATOR);
        Assert.assertNotNull(domain);
        Assert.assertEquals(creator.getName(), domain.getName());
        Assert.assertEquals(creator.getActions(), domain.getActions());
    }

    @When("I delete the last created domain")
    public void deleteLastDomain() throws Exception {
        Domain domain = (Domain) stepData.get(DOMAIN);
        KapuaLocator.getInstance().getService(DomainRegistryService.class)
                .delete(KapuaSecurityUtils.getSession().getScopeId(), domain.getId());
    }

    @Then("There is no domain")
    public void noDomain() {
        Assert.assertNull((Domain) stepData.get(DOMAIN));
    }
}
