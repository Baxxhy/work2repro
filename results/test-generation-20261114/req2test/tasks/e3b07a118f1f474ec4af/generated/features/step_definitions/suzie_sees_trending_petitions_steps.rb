Given("there has been activity on a number of petitions in the last hour") do
  # More than the three petitions displayed by the home-page trending list
  # gives the ranking a meaningful ordering as well as populating the list.
  @trending_petitions = 4.times.map do |index|
    petition = FactoryBot.create(:open_petition, action: "Trending petition #{index + 1}")

    # The creator signature is recorded by the petition factory. Add a
    # different number of recent validated signatures to make each petition
    # active during the trending window.
    (index + 1).times do
      FactoryBot.create(:validated_signature, petition: petition, validated_at: Time.current)
    end

    petition
  end
end

Given("I am on the home page") do
  visit home_url
end

Then("I should see the most popular petitions listed on the front page") do
  @trending_petitions.first(3).reverse_each do |petition|
    expect(page).to have_link(petition.action, href: petition_path(petition))
  end
end
