Given(/^a petition "([^"]*)" signed by "([^"]*)"$/) do |title, email|
  @petition = FactoryBot.create(:petition, action: title)
  FactoryBot.create(:validated_signature, petition: @petition, email: email)
end

Given("I am logged in as a moderator") do
  OmniAuth.config.mock_auth[:example] =
    FactoryBot.build(:moderator_sso_user, email: "moderator@example.com")
  visit admin_login_url
  fill_in "Email", with: "moderator@example.com"
  click_button "Sign in"
end

When("I search for a petition by id") do
  visit admin_petitions_url
  fill_in "id", with: @petition.id
  click_button "Search"
end

Then(/^I am on the admin petition page for "([^"]*)"$/) do |title|
  expect(page).to have_current_path(admin_petition_path(Petition.find_by!(action: title)))
end

When(/^I follow "([^"]*)"$/) do |link_text|
  click_link link_text
end

Then(/^I should see "([^"]*)"$/) do |text|
  expect(page).to have_text(text)
end

When(/^I search for signatures from "([^"]*)"$/) do |email|
  fill_in "q", with: email
  click_button "Search"
end

Then(/^I should see 1 signature associated with that email address$/) do
  expect(page).to have_css("tr", text: @petition.signatures.find_by!(email: "bob@example.com").email, count: 1)
end
