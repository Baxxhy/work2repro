Given(/^a petition "([^"]*)"$/) do |title|
  @petition = FactoryBot.create(:open_petition, action: title)
end

Given(/^I am logged in as a moderator$/) do
  @admin_user = FactoryBot.create(:moderator_user)
  Warden.test_mode!
  login_as(@admin_user, scope: :admin_user)
end

When(/^I view all petitions$/) do
  visit admin_petitions_path
end

When(/^I follow "([^"]*)"$/) do |text|
  click_link(text)
end

When(/^I take down the petition with a reason code "([^"]*)"$/) do |reason|
  select(reason, from: "Rejection reason")
  click_button("Email petition creator")
end

Then(/^the petition is not available for signing$/) do
  visit petition_path(@petition)
  expect(page).not_to have_link("Sign this petition")
end

Then(/^I should not be able to take down the petition$/) do
  expect(page).not_to have_select("Rejection reason")
end
