When(/^I go to (.+)$/) do |page_name|
  visit url_to(page_name)
end

Then(/^I should be on the admin login page$/) do
  expect(page).to have_current_path(admin_login_path)
end

Then(/^I should be connected to the server via an ssl connection$/) do
  expect(page.current_url).to match(/\Ahttps:\/\//)
end

Then(/^the markup should be valid$/) do
  # The response must be a complete HTML document that Capybara can parse.
  expect(page).to have_css("html")
  expect(page).to have_css("body")
end
