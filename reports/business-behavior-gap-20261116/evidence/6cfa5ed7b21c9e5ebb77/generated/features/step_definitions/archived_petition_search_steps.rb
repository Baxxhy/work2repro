Given(/^the following archived petitions exist:$/) do |table|
  table.hashes.each do |attributes|
    attributes = attributes.transform_values { |value| value == "" ? nil : value }
    attributes["signature_count"] = attributes["signature_count"].to_i if attributes["signature_count"]

    %w[opened_at closed_at created_at rejected_at].each do |date_attribute|
      attributes[date_attribute] = Date.parse(attributes[date_attribute]) if attributes[date_attribute]
    end

    traits = attributes["state"] == "rejected" ? [:rejected] : []
    FactoryBot.create(:archived_petition, *traits, **attributes.symbolize_keys)
  end
end

When(/^I go to (.+)$/) do |page_name|
  visit url_to(page_name)
end

When(/^I fill in "([^"]*)" with "([^"]*)"$/) do |field, value|
  fill_in field, with: value
end

When(/^I press "([^"]*)"$/) do |button|
  click_button button
end

Then(/^I should be on (.+)$/) do |page_name|
  expect(page).to have_current_path(url_to(page_name), ignore_query: true)
end

Then(/^I should see the following search results:$/) do |table|
  table.raw.each do |title, detail|
    expect(page).to have_text(title)
    expect(page).to have_text(detail)
  end
end

Then(/^the markup should be valid$/) do
  document = Nokogiri::HTML5(page.html)
  expect(document.at_css("html")).not_to be_nil
  expect(document.at_css("body")).not_to be_nil
end
