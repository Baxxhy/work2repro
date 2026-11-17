"""Batch trusted SHA-256 inventory without changing framing or integrity checks."""
OLD = '''        sha256sum -z -- "$path"
    done | base64 -w0)'''
NEW = '''        printf '%s\\0' "$path"
    done | xargs -0 -r sha256sum -z -- | base64 -w0)'''

def patch_support(source):
    if source.count(OLD) != 1:
        raise RuntimeError('Official inventory helper changed; review required')
    return source.replace(OLD, NEW)


# Integrity transport may wait for shared storage, while the original forward
# execution deadline remains authoritative. No test command budget is extended.
INVENTORY_TIMEOUT = 180

def install():
    from r2t.go import execution, mutation_copy
    execution._SUPPORT = patch_support(execution._SUPPORT)

    def inventory(self, *, original=False, forward=False):
        self._available()
        timeout = min(INVENTORY_TIMEOUT, self._remaining(['inventory'])) if forward else INVENTORY_TIMEOUT
        try:
            result = execution.parse_inventory(self._checked(
                'inventory', execution.ORIGINAL_ROOT if original else execution.COPY_ROOT,
                timeout=timeout))
        except BaseException:
            self.quarantined = True
            raise
        if forward:
            self._remaining(['inventory'])
        return result

    def reference_inventory(copy, root, *, forward=True):
        timeout = min(INVENTORY_TIMEOUT, copy._remaining(['mutation-reference-inventory'])) if forward else INVENTORY_TIMEOUT
        try:
            result = execution.parse_inventory(copy._checked('inventory', root, timeout=timeout))
        except BaseException:
            copy.quarantined = True
            raise
        if forward:
            copy._remaining(['mutation-reference-inventory'])
        return result

    execution.ExecutionCopy._inventory = inventory
    mutation_copy._inventory = reference_inventory
