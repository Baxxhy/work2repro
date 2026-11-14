package org.eclipse.kapua.service.user.test.r2t.generated;

import com.google.inject.Singleton;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.When;
import org.eclipse.kapua.KapuaException;
import org.eclipse.kapua.model.id.KapuaId;
import org.eclipse.kapua.locator.KapuaLocator;
import org.eclipse.kapua.plugin.sso.openid.OpenIDLocator;
import org.eclipse.kapua.plugin.sso.openid.SSOData;
import org.eclipse.kapua.qa.common.StepData;
import org.eclipse.kapua.qa.common.TestBase;
import org.eclipse.kapua.service.user.UserCreator;
import org.eclipse.kapua.service.user.UserFactory;
import org.eclipse.kapua.service.user.UserService;
import org.eclipse.kapua.service.user.steps.SSODataTest;
import org.eclipse.kapua.service.user.steps.StubOpenIDService;
import javax.inject.Inject;
import java.util.Collections;

@Singleton
public class UserServiceSteps extends TestBase {
    private static final String CREATOR = "UserCreator";

    @Inject
    public UserServiceSteps(StepData data) {
        super(data);
    }

    private StubOpenIDService stub() {
        return (StubOpenIDService) KapuaLocator.getInstance()
                .getComponent(OpenIDLocator.class).getService();
    }

    @Given("I reset SSO stub")
    public void resetSsoStub() {
        stub().reset();
    }

    @Given("brokering is enabled with no domains for current account")
    public void brokeringEnabledNoDomains() {
        SSODataTest data = SSODataTest.brokeringEnabled(Collections.emptyList());
        stub().setSSODataForAccount(getKapuaId(42), data);
    }

    @Given("External user with name {string} and external username {string} in scope with id {int}")
    public void externalUser(String name, String username, int scope) {
        UserFactory factory = KapuaLocator.getInstance().getFactory(UserFactory.class);
        UserCreator creator = factory.newCreator(getKapuaId(scope), name);
        creator.setExternalUsername(username);
        creator.setExternalId(StubOpenIDService.STUB_ID);
        stepData.put(CREATOR, creator);
    }

    @When("I create user")
    public void createUser() throws Exception {
        primeException();
        try {
            KapuaLocator.getInstance().getService(UserService.class)
                    .create((UserCreator) stepData.get(CREATOR));
        } catch (KapuaException e) {
            verifyException(e);
        }
    }
}
