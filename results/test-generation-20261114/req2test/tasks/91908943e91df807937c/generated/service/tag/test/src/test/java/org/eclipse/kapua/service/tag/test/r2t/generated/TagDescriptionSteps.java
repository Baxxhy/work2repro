package org.eclipse.kapua.service.tag.test.r2t.generated;

import javax.inject.Inject;

import com.google.inject.Singleton;
import io.cucumber.java.en.Given;
import io.cucumber.java.en.When;
import org.eclipse.kapua.KapuaException;
import org.eclipse.kapua.locator.KapuaLocator;
import org.eclipse.kapua.model.id.KapuaId;
import org.eclipse.kapua.qa.common.StepData;
import org.eclipse.kapua.service.tag.Tag;
import org.eclipse.kapua.service.tag.TagFactory;
import org.eclipse.kapua.service.tag.TagService;

@Singleton
public class TagDescriptionSteps {
    private static final String TAG_KEY = "r2t.generated.tag";

    private final StepData stepData;
    private final TagService tagService;
    private final TagFactory tagFactory;

    @Inject
    public TagDescriptionSteps(StepData stepData) {
        this.stepData = stepData;
        KapuaLocator locator = KapuaLocator.getInstance();
        this.tagService = locator.getService(TagService.class);
        this.tagFactory = locator.getFactory(TagFactory.class);
    }

    @Given("I create tag with name {string} without description")
    public void createTag(String name) throws KapuaException {
        KapuaId scopeId = KapuaId.ONE;
        Tag tag = tagService.create(tagFactory.newCreator(scopeId, name));
        stepData.put(TAG_KEY, tag);
    }

    @When("Description of tag {string} is changed into {string}")
    public void changeDescription(String name, String description) throws KapuaException {
        Tag tag = (Tag) stepData.get(TAG_KEY);
        if (tag == null || !name.equals(tag.getName())) {
            throw new IllegalStateException("No previously created tag named " + name);
        }
        tag.setDescription(description);
        stepData.put(TAG_KEY, tagService.update(tag));
    }
}
