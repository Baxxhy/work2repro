require "time"

module ArnoldSearchSteps
  def petition_step_attributes(text)
    text.scan(/(\w+):\s*("(?:[^"\\]|\\.)*"|[^,]+)/).each_with_object({}) do |(key, raw), attrs|
      value = raw.strip
      attrs[key.to_sym] =
        if value.start_with?('"')
          value[1...-1].gsub('\\"', '"')
        elsif value.match?(/\A-?\d+\z/)
          value.to_i
        else
          value
        end
    end
  end

  def petition_step_time(value)
    return nil if value.nil? || value.empty?
    return Time.zone.parse(value) if value.match?(/\A\d{4}-\d\d-\d\d\z/)

    if (match = value.match(/\A(\d+) (second|minute|hour|day|week|month|year)s? (from now|ago)\z/))
      match[1].to_i.public_send(match[2]).public_send(match[3] == "ago" ? :ago : :from_now)
    else
      value
    end
  end
end

World(ArnoldSearchSteps)

Given(/^(a|an) (pending|validated|open|closed|rejected|hidden) petition exists with (.+)$/) do |_article, state, attributes|
  attrs = petition_step_attributes(attributes)
  action = attrs.delete(:action)
  factory = state == "open" ? :open_petition : :"#{state}_petition"
  FactoryBot.create(factory, **attrs, action: action)
end

Given(/^the following archived petitions exist:$/) do |table|
  table.hashes.each do |row|
    attrs = row.each_with_object({}) { |(key, value), result| result[key.to_sym] = value unless value.nil? || value.empty? }
    %i[opened_at closed_at created_at].each do |key|
      attrs[key] = petition_step_time(attrs[key]) if attrs.key?(key)
    end
    attrs[:signature_count] = attrs[:signature_count].to_i if attrs[:signature_count]
    FactoryBot.create(:archived_petition, **attrs)
  end
end

Given(/^I am on the home page$/) do
  visit home_path
end

When(/^I search all petitions using the id of the petition "([^"]*)"$/) do |action|
  petition = Petition.find_by!(action: action)
  fill_in "search", with: petition.id
  click_button "Search petitions"
end

Then(/^I should be on the petition page for "([^"]*)"$/) do |action|
  petition = Petition.find_by!(action: action)
  expect(page).to have_current_path(petition_path(petition), ignore_query: true)
end
