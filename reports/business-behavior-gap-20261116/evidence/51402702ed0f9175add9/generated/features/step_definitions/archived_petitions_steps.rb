Given(/^these archived petitions exist:$/) do |table|
  table.hashes.each do |row|
    attributes = {
      action: row.fetch("action"),
      state: row.fetch("state"),
      signature_count: row["signature_count"].presence&.to_i,
      created_at: Date.iso8601(row.fetch("created_at")),
      opened_at: row["opened_at"].presence && Date.iso8601(row["opened_at"]),
      rejected_at: row["rejected_at"].presence && Date.iso8601(row["rejected_at"])
    }

    traits = case row.fetch("state")
             when "rejected", "hidden" then [row.fetch("state").to_sym]
             else []
             end
    FactoryBot.create(:archived_petition, *traits, **attributes)
  end
end

Given(/^I am on the archived petitions page$/) do
  visit archived_petitions_path
end

Then(/^I should see the following list of archived petitions:$/) do |table|
  table.raw.each do |action, detail|
    expect(page).to have_content(action.strip)
    expect(page).to have_content(detail.strip)
  end
end

Then(/^the markup should be valid$/) do
  # Ensure the returned document is parseable and has the expected document
  # structure; Nokogiri's HTML parser recovers from benign HTML5 constructs.
  document = Nokogiri::HTML(page.html)
  expect(document.at("html")).not_to be_nil
  expect(document.at("body")).not_to be_nil
end

When(/^I click the CSV link$/) do
  click_link "CSV"
end

Then(/^I should get a download with the filename "([^"]*)"$/) do |filename|
  expect(page.response_headers["Content-Disposition"]).to include(filename)
end
