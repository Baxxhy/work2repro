package org.eclipse.kapua.translator.test.r2t.generated;

import javax.inject.Inject;

import org.eclipse.kapua.locator.KapuaLocator;
import org.eclipse.kapua.qa.common.StepData;
import org.eclipse.kapua.translator.TranslatorHub;

import com.google.inject.Singleton;

import io.cucumber.java.en.When;

@Singleton
public class TranslatorSteps {

    private final StepData stepData;

    @Inject
    public TranslatorSteps(StepData stepData) {
        this.stepData = stepData;
    }

    @When("I try to translate from {string} to {string}")
    public void tryToTranslate(String fromClassName, String toClassName) {
        try {
            Class<?> fromClass = fromClassName.isEmpty() ? null : Class.forName(fromClassName);
            Class<?> toClass = toClassName.isEmpty() ? null : Class.forName(toClassName);
            KapuaLocator.getInstance().getService(TranslatorHub.class).getTranslatorFor(fromClass, toClass);
        } catch (Throwable e) {
            stepData.put("ExceptionCaught", true);
            stepData.put("CaughtException", e);
        }
    }
}
