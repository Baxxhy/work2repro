require "warden/test/helpers"

World(Warden::Test::Helpers)

Given(/^the time is "([^"]*)"$/) do |time|
  Timecop.freeze(Time.zone.parse(time))
end

Given(/^I am logged in as a sysadmin with the email "([^"]*)", first_name "([^"]*)", last_name "([^"]*)"$/) do |email, first_name, last_name|
  user = FactoryBot.create(
    :sysadmin_user,
    email: email,
    first_name: first_name,
    last_name: last_name
  )
  login_as(user, scope: :user)
end

Given(/^a moderator user exists with email: "([^"]*)", first_name: "([^"]*)", last_name: "([^"]*)"$/) do |email, first_name, last_name|
  FactoryBot.create(
    :moderator_user,
    email: email,
    first_name: first_name,
    last_name: last_name
  )
end

Given(/^(\d+) moderator users exist$/) do |count|
  FactoryBot.create_list(:moderator_user, count.to_i)
end

When(/^I go to the admin users index page$/) do
  visit admin_admin_users_path
end

When(/^I follow "([^"]*)"$/) do |link_text|
  click_link(link_text)
end

Then(/^I should see (\d+) rows in the admin user table$/) do |count|
  expect(page).to have_css("table tbody tr", count: count.to_i)
end
