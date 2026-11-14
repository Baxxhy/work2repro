package org.eclipse.kapua.service.job.test.r2t.generated;

import javax.inject.Inject;

import com.google.inject.Singleton;
import io.cucumber.java.en.And;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.When;
import org.eclipse.kapua.KapuaException;
import org.eclipse.kapua.locator.KapuaLocator;
import org.eclipse.kapua.qa.common.StepData;
import org.eclipse.kapua.qa.common.TestBase;
import org.eclipse.kapua.service.job.step.definition.JobStepDefinition;
import org.eclipse.kapua.service.job.step.definition.JobStepDefinitionCreator;
import org.eclipse.kapua.service.job.step.definition.JobStepDefinitionFactory;
import org.eclipse.kapua.service.job.step.definition.JobStepDefinitionService;

@Singleton
public class JobStepDefinitionSteps extends TestBase {
    private static final String CREATOR = "JobStepDefinitionCreator";

    @Inject
    public JobStepDefinitionSteps(StepData stepData) {
        super(stepData);
    }

    @Given("A regular step definition creator with the name {string}")
    public void regularCreator(String name) {
        JobStepDefinitionFactory factory = KapuaLocator.getInstance().getFactory(JobStepDefinitionFactory.class);
        JobStepDefinitionCreator creator = factory.newCreator(getCurrentScopeId());
        creator.setName(name);
        stepData.put(CREATOR, creator);
    }

    @And("I set the step definition creator name to null")
    public void setCreatorNameNull() {
        ((JobStepDefinitionCreator) stepData.get(CREATOR)).setName(null);
    }

    @When("I create a new step definition entity from the existing creator")
    public void createFromCreator() throws Exception {
        primeException();
        try {
            JobStepDefinitionCreator creator = (JobStepDefinitionCreator) stepData.get(CREATOR);
            JobStepDefinition result = KapuaLocator.getInstance()
                    .getService(JobStepDefinitionService.class).create(creator);
            stepData.put("JobStepDefinition", result);
        } catch (KapuaException e) {
            verifyException(e);
        }
    }
}
