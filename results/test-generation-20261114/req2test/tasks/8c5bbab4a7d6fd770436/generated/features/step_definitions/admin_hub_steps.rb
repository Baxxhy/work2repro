Given(/^I am logged in as a moderator$/) do
  @admin_user = FactoryBot.create(:moderator_user, email: "moderator@example.com")
  OmniAuth.config.test_mode = true
  OmniAuth.config.mock_auth[:example] = OmniAuth::AuthHash.new(
    provider: "example",
    uid: @admin_user.email,
    info: {
      email: @admin_user.email,
      first_name: @admin_user.first_name,
      last_name: @admin_user.last_name
    },
    extra: { raw_info: { roles: ["moderator"] } }
  )
  page.driver.get("/auth/example/callback")
end

Given(/^(\d+) petitions exist with state: "([^"]*)"$/) do |count, state|
  factory = "#{state}_petition"
  Integer(count).times { FactoryBot.create(factory.to_sym) }
end

Given(/^there are (\d+) petitions awaiting a Government response$/) do |count|
  Integer(count).times do
    FactoryBot.create(:petition,
      response_threshold_reached_at: 1.day.ago,
      response_state: "awaiting")
  end
end

Given(/^there are (\d+) petitions with a scheduled debate date$/) do |count|
  Integer(count).times { FactoryBot.create(:petition, :scheduled_for_debate) }
end

Given(/^there are (\d+) petitions with enough signatures to require a debate$/) do |count|
  threshold = Parliament.current.debate_threshold
  Integer(count).times do
    FactoryBot.create(:petition, signature_count: threshold,
      debate_threshold_reached_at: 1.day.ago)
  end
end

When(/^I go to the Admin home page$/) do
  visit url_to("the Admin home page")
end

Then(/^I should see "([^"]*)"$/) do |text|
  expect(page).to have_content(text)
end

Then(/^I should see a link called "([^"]*)" linking to "([^"]*)"$/) do |label, href|
  expect(page).to have_xpath("//a[normalize-space(.)=#{XPathHelpers.literal(label)} and @href=#{XPathHelpers.literal(href)}]")
end

Then(/^I should be connected to the server via an ssl connection$/) do
  expect(page.current_url).to start_with("https://")
end

Then(/^the markup should be valid$/) do
  document = Nokogiri::HTML(page.html)
  expect(document.errors).to be_empty
end
