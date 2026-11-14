package org.eclipse.kapua.service.user.test.r2t.generated;

import java.util.Collections;

import javax.inject.Inject;

import org.eclipse.kapua.model.id.KapuaEid;
import org.eclipse.kapua.plugin.sso.openid.OpenIDLocator;
import org.eclipse.kapua.qa.common.StepData;
import org.eclipse.kapua.service.user.UserCreator;
import org.eclipse.kapua.service.user.UserFactory;
import org.eclipse.kapua.service.user.UserService;
import org.eclipse.kapua.service.user.UserType;
import org.eclipse.kapua.service.user.steps.SSODataTest;
import org.eclipse.kapua.service.user.steps.StubOpenIDService;
import org.eclipse.kapua.locator.KapuaLocator;
import org.junit.Assert;

import com.google.inject.Singleton;

import io.cucumber.java.en.Given;
import io.cucumber.java.en.When;

@Singleton
public class UserServiceSteps {

    private final StepData stepData;
    private final StubOpenIDService openIDService;

    @Inject
    public UserServiceSteps(StepData stepData) {
        this.stepData = stepData;
        this.openIDService = (StubOpenIDService) KapuaLocator.getInstance()
                .getService(OpenIDLocator.class).getService();
    }

    @Given("I reset SSO stub")
    public void resetSsoStub() {
        openIDService.reset();
    }

    @Given("brokering is enabled with null domains for current account")
    public void brokeringEnabledWithNullDomains() {
        SSODataTest data = SSODataTest.brokeringEnabled(null);
        openIDService.setSSODataForAccount(new KapuaEid(java.math.BigInteger.valueOf(42)), data);
    }

    @Given("External user with name {string} and external username {string} in scope with id {int}")
    public void externalUser(String name, String username, Integer scopeId) {
        UserFactory factory = KapuaLocator.getInstance().getFactory(UserFactory.class);
        UserCreator creator = factory.newCreator(new KapuaEid(java.math.BigInteger.valueOf(scopeId)), name);
        creator.setUserType(UserType.EXTERNAL);
        creator.setExternalUsername(username);
        stepData.put("UserCreator", creator);
    }

    @When("I create user")
    public void createUser() {
        stepData.put("ExceptionCaught", false);
        try {
            KapuaLocator.getInstance().getService(UserService.class)
                    .create((UserCreator) stepData.get("UserCreator"));
        } catch (Exception exception) {
            Assert.assertEquals("KapuaIllegalArgumentException", exception.getClass().getSimpleName());
            Assert.assertTrue(exception.getMessage(), exception.getMessage().contains("An illegal value was provided"));
            stepData.put("ExceptionCaught", true);
            stepData.put("Exception", exception);
        }
    }
}
