require "json"

Given("a set of petitions") do
  FactoryBot.create_list(:open_petition, 3)
end

Given("I am on the all petitions page") do
  visit url_to("the all petitions page")
end

Then("I should see {int} petitions") do |count|
  expect(page).to have_css("li.petition-item", count: count)
end

Then("the markup should be valid") do
  document = Nokogiri::HTML(page.html)
  expect(document.at("html")).not_to be_nil
  expect(document.at("body")).not_to be_nil
end

When("I click the JSON link") do
  click_link "JSON"
end

Then("I should be on the all petitions JSON page") do
  expect(page).to have_current_path(url_to("the all petitions JSON page"), ignore_query: true)
end

Then("the JSON should be valid") do
  expect { JSON.parse(page.body) }.not_to raise_error
end
