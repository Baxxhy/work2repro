Given('a petition {string} exists and hasn’t passed the threshold for a debate') do |title|
  FactoryBot.create(:open_petition, action: title, debate_threshold_reached_at: nil)
end

Given('a petition {string} passed the threshold for a debate less than a day ago and has no debate date set') do |title|
  FactoryBot.create(
    :awaiting_debate_petition,
    action: title,
    debate_threshold_reached_at: 1.hour.ago,
    debate_scheduled_at: nil,
    scheduled_debate_date: nil
  )
end

Given('a petition {string} passed the threshold for a debate {int} days ago and has no debate date set') do |title, days|
  FactoryBot.create(
    :awaiting_debate_petition,
    action: title,
    debate_threshold_reached_at: days.days.ago,
    debate_scheduled_at: nil,
    scheduled_debate_date: nil
  )
end

Given('a petition {string} passed the threshold for a debate {int} days ago and has a debate in {int} days') do |title, days_ago, days_until|
  FactoryBot.create(
    :scheduled_debate_petition,
    action: title,
    debate_threshold_reached_at: days_ago.days.ago,
    debate_scheduled_at: days_ago.days.ago,
    scheduled_debate_date: days_until.days.from_now
  )
end

When('I browse to see only {string} petitions') do |filter|
  visit petitions_url
  click_link filter
end

Then('I should see {string}') do |text|
  expect(page).to have_content(text)
end

Then('I should see the following ordered list of petitions:') do |titles|
  text = page.text
  positions = titles.raw.flatten.map do |title|
    expect(page).to have_content(title)
    text.index(title)
  end
  expect(positions).to eq(positions.sort)
end

Then('the markup should be valid') do
  document = Nokogiri::HTML5(page.html)
  expect(document.at_css('html')).not_to be_nil
  expect(document.at_css('body')).not_to be_nil
  ids = document.css('[id]').map { |element| element['id'] }
  expect(ids.uniq).to eq(ids)
end
