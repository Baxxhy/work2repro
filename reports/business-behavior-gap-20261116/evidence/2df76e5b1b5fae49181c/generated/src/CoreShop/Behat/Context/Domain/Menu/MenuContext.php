<?php

declare(strict_types=1);

namespace CoreShop\Behat\Context\Domain\Menu;

use Behat\Behat\Context\Context;
use CoreShop\Bundle\MenuBundle\Builder;
use Knp\Menu\ItemInterface;
use Webmozart\Assert\Assert;

final class MenuContext implements Context
{
    public function __construct(private readonly Builder $menuBuilder)
    {
    }

    /**
     * @Then /^the menu "([^"]+)" should have a child with ID "([^"]+)"$/
     * @Then /^the menu "([^"]+)" child with id "([^"]+)" should have a child with ID "([^"]+)"$/
     */
    public function menuShouldHaveChild(string $menuName, string $parentOrChild, ?string $childId = null): void
    {
        // The CoreShop admin menu is assembled by the main-menu builder. The
        // name in the feature identifies that menu; its root is built here.
        Assert::same($menuName, 'coreshop.main');
        $menu = $this->menuBuilder->createMenu();

        if ($childId === null) {
            $parent = $menu;
            $childId = $parentOrChild;
        } else {
            $parent = $menu->getChild($parentOrChild);
            Assert::notNull($parent, sprintf('Menu "%s" has no child "%s".', $menuName, $parentOrChild));
        }

        Assert::true(
            $this->hasChild($parent, $childId),
            sprintf('Menu "%s" has no child "%s".', $menuName, $childId),
        );
    }

    private function hasChild(ItemInterface $menu, string $id): bool
    {
        return $menu->getChild($id) !== null;
    }
}
