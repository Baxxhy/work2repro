package org.eclipse.kapua.integration.service.authorization.r2t.generated;

import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;
import org.eclipse.kapua.locator.KapuaLocator;
import org.eclipse.kapua.model.id.KapuaId;
import org.eclipse.kapua.qa.common.cucumber.CucDomain;
import org.eclipse.kapua.service.authentication.AuthenticationService;
import org.eclipse.kapua.service.authentication.CredentialsFactory;
import org.eclipse.kapua.service.authorization.domain.Domain;
import org.eclipse.kapua.service.authorization.domain.DomainCreator;
import org.eclipse.kapua.service.authorization.domain.DomainFactory;
import org.eclipse.kapua.service.authorization.domain.DomainRegistryService;
import org.junit.Assert;

import java.util.List;

public class DomainFindSteps {
    private final KapuaLocator locator = KapuaLocator.getInstance();
    private DomainCreator creator;
    private Domain created;
    private Domain found;

    @When("I login as user with name {string} and password {string}")
    public void login(String username, String password) throws Exception {
        locator.getService(AuthenticationService.class).login(
                locator.getFactory(CredentialsFactory.class)
                        .newUsernamePasswordCredentials(username, password));
    }

    @Given("I create the domain")
    public void createDomain(List<CucDomain> rows) throws Exception {
        CucDomain data = rows.get(0);
        DomainFactory factory = locator.getFactory(DomainFactory.class);
        creator = factory.newCreator(data.getName());
        data.doParse();
        creator.setActions(data.getActionSet());
        creator.setServiceName(data.getServiceName());
        created = locator.getService(DomainRegistryService.class).create(creator);
    }

    @When("I search for the last created domain")
    public void findLastCreatedDomain() throws Exception {
        found = locator.getService(DomainRegistryService.class)
                .find(KapuaId.ONE, created.getId());
    }

    @Then("The domain matches the creator")
    public void domainMatchesCreator() {
        Assert.assertNotNull("Domain should be found by its ID", found);
        Assert.assertEquals(creator.getName(), found.getName());
        Assert.assertEquals(creator.getActions(), found.getActions());
    }
}
