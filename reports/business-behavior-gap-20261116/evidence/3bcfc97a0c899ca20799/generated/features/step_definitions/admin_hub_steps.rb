Given("I am logged in as a moderator") do
  OmniAuth.config.test_mode = true
  OmniAuth.config.mock_auth[:example] = FactoryBot.build(:moderator_sso_user)
  visit admin_login_url
  fill_in "Email", with: "moderator@example.com"
  click_button "Sign in"
end

Given("{int} petitions exist with state: {string}") do |count, state|
  FactoryBot.create_list(:"#{state}_petition", count.to_i)
end

When("I go to the Admin home page") do
  visit url_to("the Admin home page")
end

When("I follow {string}") do |link_text|
  click_link link_text
end

Then("I should be on the Admin all petitions page") do
  expect(page).to have_current_path(admin_petitions_path, ignore_query: true)
end
