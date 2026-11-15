Given(/^I am logged in as a moderator$/) do
  @admin_sso_user = FactoryBot.build(:moderator_sso_user)
  OmniAuth.config.mock_auth[:example] = @admin_sso_user
  visit "/admin/auth/example/callback"
end

Given(/^I log out and login back in as a sysadmin$/) do
  visit "/admin/logout"
  @admin_sso_user = FactoryBot.build(:sysadmin_sso_user)
  OmniAuth.config.mock_auth[:example] = @admin_sso_user
  visit "/admin/auth/example/callback"
end

Given(/^an open petition exists with action: "([^"]*)"$/) do |action|
  FactoryBot.create(:open_petition, action: action)
end

When(/^I view all petitions$/) do
  visit url_to("the Admin all petitions page")
end

Then(/^I should see "([^"]*)"$/) do |text|
  expect(page).to have_text(text)
end
