require "uri"

Given(/a (pending|validated|open|closed|rejected|hidden) petition exists with (.+)/) do |state, attributes|
  attrs = {}
  attributes.scan(/([a-z_]+):\s*"([^"]*)"(?:,?\s*|$)/) do |key, value|
    attrs[key.to_sym] = value
  end

  %i[closed_at].each do |key|
    next unless attrs[key]

    expression = attrs[key]
    attrs[key] = if expression.match?(/\A\d+\s+(?:second|minute|hour|day|week|month|year)s?\s+(?:from now|ago)\z/)
      amount, unit, direction = expression.match(/\A(\d+)\s+(\w+)\s+(from now|ago)\z/).captures
      amount.to_i.public_send(unit.pluralize).public_send(direction == "ago" ? :ago : :from_now)
    else
      expression
    end
  end

  FactoryBot.create(:"#{state}_petition", **attrs)
end

Given("the following archived petitions exist:") do |table|
  table.hashes.each do |row|
    attrs = row.slice("action", "state", "signature_count").transform_keys(&:to_sym)
    %w[opened_at closed_at created_at].each do |key|
      attrs[key.to_sym] = Date.parse(row[key]) if row[key].to_s != ""
    end
    FactoryBot.create(:archived_petition, **attrs)
  end
end

Given("I am on the home page") do
  visit home_url
end

When('I search all petitions for {string}') do |term|
  fill_in "search", with: term
  click_button "Search"
end

Then("I should be on the all petitions page") do
  expect(URI.parse(current_url).path).to eq(petitions_path)
end

Then("I should have the following query string:") do |table|
  query = URI.decode_www_form(URI.parse(current_url).query.to_s).to_h
  table.raw.each { |key, value| expect(query[key]).to eq(value.strip) }
end

Then('I should see my search term {string} filled in the search field') do |term|
  expect(page).to have_field("search", with: term)
end

Then("I should see {string}") do |text|
  expect(page).to have_content(text)
end

Then("I should see the following search results:") do |table|
  results = table.raw
  result_rows = page.all("ul.petition-lists > li")
  expect(result_rows.length).to eq(results.length)
  results.each_with_index do |(action, detail), index|
    expect(result_rows[index]).to have_content(action)
    expect(result_rows[index]).to have_content(detail)
  end
end
