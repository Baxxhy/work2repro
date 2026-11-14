Given(/^a petition "([^"]*)" has been rejected$/) do |title|
  FactoryBot.create(:rejected_petition, action: title)
end

When(/^I browse to see only "([^"]*)" petitions$/) do |status|
  visit petitions_url(status: status.downcase)
end

Then(/^I should see "([^"]*)"$/) do |text|
  expect(page).to have_content(text)
end

Then(/^I should see the following ordered list of petitions:$/) do |titles|
  expected = titles.raw.flatten.map(&:strip)
  actual = page.all("ol li").map { |item| item.text.strip }
  expect(actual).to eq(expected)
end

Then(/^the markup should be valid$/) do
  expect(page.status_code).to eq(200)
  expect(Nokogiri::HTML(page.html).errors).to be_empty
end
