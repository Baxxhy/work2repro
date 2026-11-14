Given(/^a constituency "([^"]+)"(?: with MP "([^"]+)")? is found by postcode "([^"]+)"$/) do |name, mp, postcode|
  slug = name.parameterize
  constituency = Constituency.find_or_initialize_by(slug: slug)
  constituency.assign_attributes(
    name: name, external_id: "test-#{slug}", ons_code: "E99999999",
    mp_id: (mp ? "test-mp-#{slug}" : nil), mp_name: mp,
    mp_date: Date.current, example_postcode: postcode.delete(" ").upcase
  )
  constituency.save!
  @constituencies ||= {}
  @constituencies[name] = constituency

  member = mp ? "<RepresentingMember><Member_Id>#{constituency.mp_id}</Member_Id><Member>#{mp}</Member><StartDate>2015-05-07T00:00:00</StartDate></RepresentingMember>" : ""
  xml = "<Constituencies><Constituency><Constituency_Id>#{constituency.external_id}</Constituency_Id><Name>#{name}</Name><ONSCode>#{constituency.ons_code}</ONSCode><RepresentingMembers>#{member}</RepresentingMembers></Constituency></Constituencies>"
  stub_api_request_for(PostcodeSanitizer.call(postcode)).to_return(api_response(:ok) { xml })
end

Given(/^an (open|closed) petition "([^"]+)" with some signatures$/) do |status, title|
  @petitions ||= {}
  petition = if status == "closed"
    FactoryBot.create(:validated_petition, :closed, action: title)
  else
    FactoryBot.create(:validated_petition, action: title)
  end
  @petitions[title] = petition
end

Given(/^(a|few|some|many) constituents in "([^"]+)" support "([^"]+)"$/) do |amount, constituency_name, title|
  constituency = @constituencies.fetch(constituency_name)
  petition = @petitions.fetch(title)
  count = case amount
    when "few" then 3
    when "many" then 10
    else 5
  end
  count.times do
    signature = FactoryBot.create(:validated_signature, petition: petition, postcode: constituency.example_postcode)
    signature.update_column(:constituency_id, constituency.external_id)
  end
end

Given(/^the MP has passed away$/) do
  # The historical constituency API response identifies Harry Harpham as the
  # sitting member for this scenario; the page should omit a deceased MP link.
  @constituencies.each_value do |constituency|
    next unless constituency.mp_name == "Harry Harpham"
    constituency.update!(mp_name: nil, mp_id: nil)
  end
end

When(/^I am on the local petitions page$/) do
  visit local_petitions_url
end

When(/^I search for petitions local to me in "([^"]+)"$/) do |postcode|
  fill_in "postcode", with: PostcodeSanitizer.call(postcode)
  click_button "Search"
end

When(/^I click the view all local petitions$/) do
  click_link(/view all/i)
end

When(/^I click the CSV link$/) do
  click_link(/CSV/i)
end

Then(/^I should be on the all local petitions results page$/) do
  expect(page.current_path).to include("/petitions/local/")
  expect(page.current_path).to end_with("/all")
end

Then(/^the markup should be valid$/) do
  expect(page).to have_xpath("/html/body")
end

Then(/^I should get a download with the filename "([^"]+)"$/) do |filename|
  expect(page.response_headers["Content-Disposition"]).to include(filename)
end
