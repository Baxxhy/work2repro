# Req2Test真实需求全文

## python-docx

```gherkin
Scenario: Document.add_section() adds a section that inherits headers and footers
    Given a single-section Document object with headers and footers as document
     When I execute section = document.add_section()
     Then section.header.is_linked_to_previous is True
      And section.even_page_header.is_linked_to_previous is True
      And section.first_page_header.is_linked_to_previous is True
      And section.footer.is_linked_to_previous is True
      And section.even_page_footer.is_linked_to_previous is True
      And section.first_page_footer.is_linked_to_previous is True
```

## e-petitions

```gherkin
Scenario: Charlie has to search for a petition before creating one
  Given the following petitions exist:
    | action                         | state    | signature_count | open_at    |
    | Rioters should loose benefits  | open     |             835 | 2011-08-11 |
    | Rioters must loose benefits    | rejected |               5 |            |
    | Do not remove rioters benefits | open     |            1023 | 2011-08-21 |
  And I am on the home page
  When I follow "Start a petition" within ".//main"
  Then I should see "Start a petition"
  When I follow "Start your petition"
  Then I should be asked to confirm my eligibility
  When I confirm that I am UK citizen or resident
  Then I should see "Petition title"
  When I fill in "Petition title" with "Rioters benefits"
  And I press "Continue"
  Then I should see the following similar petitions:
    | Do not remove rioters benefits | Total signatures 1,023 |
    | Rioters should loose benefits  | Total signatures 835   |
  When I press "Continue with my petition"
  Then I should see "Say what you want the UK Government or Parliament to do"
```
