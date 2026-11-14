When(/^I go to (.+)$/) do |page_name|
  visit url_to(page_name)
end

When(/^I follow "([^"]*)" within "([^"]*)"$/) do |link_text, locator|
  within(selector_for(locator)) do
    click_link(link_text)
  end
end

Then(/^I should be on (.+)$/) do |page_name|
  expect(current_path).to eq(URI.parse(url_to(page_name)).path)
end

Then(/^I should see "([^"]*)" in the browser page title$/) do |text|
  expect(page.title).to include(text)
end

Then(/^the markup should be valid$/) do
  document = Nokogiri::HTML(page.html)
  expect(document.at('html')).not_to be_nil
  expect(document.at('body')).not_to be_nil
end
