Given(/^a petition "([^"]*)" exists with a signature count of (\d+)$/) do |name, count|
  petition = FactoryBot.create(:open_petition, action: name)
  petition.update_column(:signature_count, count.to_i)
end

When(/^I browse to see only "([^"]*)" petitions$/) do |state|
  visit petitions_path(state: state.downcase)
end

Then(/^I should see "([^"]*)"$/) do |text|
  expect(page).to have_text(text)
end

Then(/^I should see the following ordered list of petitions:$/) do |table|
  expected = table.raw.flatten.map(&:strip)
  actual = page.all("ul.petition-lists li").map { |item| item.text.strip }
  expect(actual).to eq(expected)
end

Then(/^the markup should be valid$/) do
  expect(page).to have_css("html > body")
end
