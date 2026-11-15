Given(/^I am logged in as a sysadmin with the email "([^"]+)", first_name "([^"]+)", last_name "([^"]+)"$/) do |email, first_name, last_name|
  auth = FactoryBot.build(
    :sysadmin_sso_user,
    email: email,
    first_name: first_name,
    last_name: last_name
  )
  OmniAuth.config.mock_auth[:example] = auth
  visit "/admin/auth/example/callback"
end

When(/^I go to (.+)$/) do |page_name|
  visit url_to(page_name)
end

Then(/^I should not see "([^"]*)"$/) do |text|
  expect(page).not_to have_text(text)
end
