Given(/^petitions are not collecting signatures$/) do
  Site.update!(disable_collecting_signatures: true)
end

When(/^I go to (.+)$/) do |page_name|
  visit url_to(page_name)
end

Then(/^I should see "([^"]*)"$/) do |text|
  expect(page).to have_text(text)
end
