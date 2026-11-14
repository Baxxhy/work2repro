Given("the following petitions exist:") do |table|
  table.hashes.each do |attributes|
    attributes["signature_count"] = attributes["signature_count"].to_i
    attributes["open_at"] = nil if attributes["open_at"].to_s.empty?
    FactoryBot.create(:petition, **attributes.symbolize_keys, increment: false)
  end
end

Given(/^I am on the (.+)$/) do |page_name|
  visit url_to("the #{page_name}")
end

When(/^I follow "([^"]*)"(?: within "([^"]*)")?$/) do |link, scope|
  if scope
    within(:xpath, scope) { click_link(link) }
  else
    click_link(link)
  end
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

Then("I should be asked to confirm my eligibility") do
  expect(page).to have_content("Are you a British citizen or UK resident?")
end

When("I confirm that I am UK citizen or resident") do
  choose("Yes")
  click_button("Continue")
end

Then("I should see the following similar petitions:") do |table|
  table.raw.each do |action, signatures|
    expect(page).to have_content(action)
    expect(page).to have_content(signatures)
  end
end
