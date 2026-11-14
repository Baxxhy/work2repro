<?php

namespace Tests\Integration\Behaviour\Features\Context;

use Behat\Gherkin\Node\TableNode;
use Language;
use Meta;
use PrestaShop\PrestaShop\Core\Domain\Meta\Command\AddMetaCommand;
use PrestaShop\PrestaShop\Core\Domain\Meta\ValueObject\MetaId;
use RuntimeException;
use Tests\Integration\Behaviour\Features\Context\Domain\AbstractDomainFeatureContext;

class MetaFeatureContext extends AbstractDomainFeatureContext
{
    /**
     * @Given language with iso code :isoCode is the default one
     */
    public function setDefaultLanguageByIsoCode(string $isoCode): void
    {
        $languageId = (int) Language::getIdByIso($isoCode);
        if (!$languageId || $languageId !== $this->getDefaultLangId()) {
            throw new RuntimeException(sprintf('Language "%s" is not the default language', $isoCode));
        }
        $this->getSharedStorage()->set('default_language_id', $languageId);
    }

    /**
     * @When I add meta :reference with specified properties
     */
    public function addMeta(string $reference, TableNode $table): void
    {
        $properties = $table->getRowsHash();
        $languageId = $this->getDefaultLangId();
        $command = new AddMetaCommand($properties['pageName']);
        if (isset($properties['localisedPageTitle'])) {
            $command->setLocalisedPageTitle([$languageId => $properties['localisedPageTitle']]);
        }
        if (isset($properties['localisedMetaDescription'])) {
            $command->setLocalisedMetaDescription([$languageId => $properties['localisedMetaDescription']]);
        }
        if (isset($properties['localisedRewriteUrls'])) {
            $command->setLocalisedRewriteUrls([$languageId => $properties['localisedRewriteUrls']]);
        }

        /** @var MetaId $metaId */
        $metaId = $this->getCommandBus()->handle($command);
        $this->getSharedStorage()->set($reference, $metaId->getValue());
    }

    /**
     * @Then meta :reference page should be :pageName
     */
    public function assertMetaPage(string $reference, string $pageName): void
    {
        $meta = new Meta($this->referenceToId($reference));
        $this->assertSameValue($pageName, $meta->page);
    }

    /**
     * @Then meta :reference field :field for default language should be :expected
     */
    public function assertMetaField(string $reference, string $field, string $expected): void
    {
        if (!in_array($field, ['title', 'description', 'url_rewrite'], true)) {
            throw new RuntimeException(sprintf('Unsupported meta field "%s"', $field));
        }
        $meta = new Meta($this->referenceToId($reference), $this->getDefaultLangId());
        $this->assertSameValue($expected, $meta->{$field});
    }

    private function assertSameValue(string $expected, $actual): void
    {
        if ((string) $actual !== $expected) {
            throw new RuntimeException(sprintf('Expected "%s", got "%s"', $expected, (string) $actual));
        }
    }
}
