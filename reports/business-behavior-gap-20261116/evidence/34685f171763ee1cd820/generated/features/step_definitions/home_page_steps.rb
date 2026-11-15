Given("petitions are collecting signatures") do
  Site.update!(disable_collecting_signatures: false)
end

When("I go to the home page") do
  visit url_to("the home page")
end

Then("I should not see {string}") do |text|
  expect(page).not_to have_text(text)
end
