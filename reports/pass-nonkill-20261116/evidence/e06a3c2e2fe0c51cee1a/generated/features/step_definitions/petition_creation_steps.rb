Given(/^I am on (.+)$/) do |page_name|
  visit url_to(page_name)
end

When(/^I follow "([^"]*)"$/) do |link|
  click_link(link)
end

Then(/^I should be asked to confirm my eligibility$/) do
  expect(page).to have_content("Are you a British citizen or UK resident?")
end

When(/^I confirm that I am UK citizen or resident$/) do
  choose("Yes")
  click_button("Continue")
end

Then(/^I should see "([^"]*)"$/) do |text|
  expect(page).to have_content(text)
end

When(/^I fill in "([^"]*)" with "([^"]*)"$/) do |field, value|
  fill_in(field, with: value)
end

When(/^I press "([^"]*)"$/) do |button|
  click_button(button)
end

Then(/^the markup should be valid$/) do
  document = Nokogiri::HTML5(page.body)
  expect(document.at_css("html")).not_to be_nil
  # User-supplied petition text must be rendered as text, never as an event
  # handler or other executable HTML attribute.
  expect(document.css("[onmouseover]").to_a).to be_empty
end
