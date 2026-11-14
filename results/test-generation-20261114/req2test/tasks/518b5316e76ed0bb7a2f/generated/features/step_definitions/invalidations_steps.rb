require "factory_bot"

World(FactoryBot::Syntax::Methods)

When("I am logged in as a sysadmin") do
  user = create(:sysadmin_user)
  login_as(user, scope: :user)
end

When("I am on the admin invalidations page") do
  visit admin_invalidations_path
end

When("I follow {string}") do |label|
  click_link(label)
end

When("I fill in {string} with {string}") do |field, value|
  fill_in(field, with: value)
end

When("I press {string}") do |button|
  click_button(button)
end

Then("I should see {string}") do |text|
  expect(page).to have_text(text)
end

Then("I should see an invalidation status of {string}") do |status|
  expect(page).to have_text(status)
end
