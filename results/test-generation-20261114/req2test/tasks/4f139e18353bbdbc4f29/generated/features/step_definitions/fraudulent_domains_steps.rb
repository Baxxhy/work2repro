Given(/^an open petition "([^"]*)" with some fraudulent signatures$/) do |action|
  @petition = FactoryBot.create(:open_petition, action: action)
  2.times do |n|
    FactoryBot.create(
      :fraudulent_signature,
      petition: @petition,
      email: "fraudulent#{n}@example.org"
    )
  end
end

Given(/^I am logged in as a moderator$/) do
  @admin_user = FactoryBot.create(:moderator_user)
  Warden.test_mode!
  login_as(@admin_user, scope: :user)
end

When(/^I view all petitions$/) do
  visit url_to("the Admin all petitions page")
end

When(/^I follow "([^"]*)"$/) do |link|
  click_link(link)
end

Then(/^I should not see "([^"]*)"$/) do |text|
  expect(page).not_to have_text(text)
end
