package org.eclipse.kapua.service.account.test.r2t.generated;

import javax.inject.Inject;

import org.eclipse.kapua.KapuaException;
import org.eclipse.kapua.commons.model.id.IdGenerator;
import org.eclipse.kapua.commons.model.id.KapuaEid;
import org.eclipse.kapua.locator.KapuaLocator;
import org.eclipse.kapua.qa.common.StepData;
import org.eclipse.kapua.service.account.AccountService;

import io.cucumber.java.en.When;

public class DeleteNonexistingAccountSteps {
    private static final String EXCEPTION_CAUGHT = "ExceptionCaught";

    private final StepData stepData;

    @Inject
    public DeleteNonexistingAccountSteps(StepData stepData) {
        this.stepData = stepData;
    }

    @When("I delete a random account")
    public void deleteRandomAccount() {
        try {
            KapuaLocator.getInstance().getService(AccountService.class)
                    .delete(new KapuaEid(IdGenerator.generate()), new KapuaEid(IdGenerator.generate()));
        } catch (KapuaException e) {
            stepData.put(EXCEPTION_CAUGHT, true);
            return;
        }
        stepData.put(EXCEPTION_CAUGHT, false);
    }
}
