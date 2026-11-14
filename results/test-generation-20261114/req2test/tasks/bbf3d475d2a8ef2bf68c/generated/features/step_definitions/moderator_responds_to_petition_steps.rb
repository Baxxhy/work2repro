Given('I am logged in as a moderator named {string}') do |name|
  first_name, last_name = name.split(' ', 2)
  OmniAuth.config.mock_auth[:example] = FactoryBot.build(
    :moderator_sso_user,
    first_name: first_name,
    last_name: last_name,
    email: "#{name.downcase.tr(' ', '.')}@example.com"
  )
  visit '/admin/auth/example'
end

Given('a sponsored petition exists with action: {string}') do |action|
  @petition = FactoryBot.create(:sponsored_petition, action: action)
end

When('I go to the admin petition page for {string}') do |action|
  visit url_to(%(the admin petition page for "#{action}"))
end

When('I reject the petition with a reason code {string}') do |reason|
  select reason, from: 'Rejection reason'
  click_button 'Reject'
end

Then('a petition should exist with action: {string}, state: {string}') do |action, state|
  expect(Petition.find_by!(action: action).state).to eq(state)
end

Then('I should see {string}') do |text|
  expect(page).to have_text(text)
end
