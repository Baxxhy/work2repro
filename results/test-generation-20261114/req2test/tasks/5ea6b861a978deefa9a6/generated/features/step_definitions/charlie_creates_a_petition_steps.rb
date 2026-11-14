Given(/^Parliament is dissolving$/) do
  FactoryBot.create(:parliament, :dissolving)
  Parliament.reload
end

Given(/^I am on (.+)$/) do |page_name|
  visit url_to(page_name)
end

Then(/^I should see the Parliament dissolution warning message$/) do
  expect(page).to have_content("Parliament is dissolving")
  expect(page).to have_content("This means all petitions will close in 2 weeks")
end
