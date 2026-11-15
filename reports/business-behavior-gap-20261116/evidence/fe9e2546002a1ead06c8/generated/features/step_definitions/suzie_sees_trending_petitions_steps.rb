Given(/^I am on the home page$/) do
  visit url_to("the home page")
end

Then(/^I should not see the trending petitions section$/) do
  expect(page).not_to have_text(/trending petitions/i)
end
