Given('the following archived petitions exist:') do |table|
  table.hashes.each do |attributes|
    attributes.transform_values! { |value| value == '' ? nil : value }
    attributes['signature_count'] = attributes['signature_count'].to_i if attributes['signature_count']

    traits = attributes['state'] == 'rejected' ? [:rejected] : []
    FactoryBot.create(:archived_petition, *traits, **attributes.symbolize_keys)
  end
end

When('I go to the archived petitions page') do
  visit archived_petitions_path
end

When('I fill in "search" with the id of the archived petition {string}') do |action|
  petition = Archived::Petition.find_by!(action: action)
  fill_in 'search', with: petition.id
end

When('I press {string}') do |button|
  click_button(button)
end

Then('I should be on the archived petition page for {string}') do |action|
  petition = Archived::Petition.find_by!(action: action)
  expect(page).to have_current_path(archived_petition_path(petition))
end
