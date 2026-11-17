"""Batch trusted SHA-256 inventory without changing framing or integrity checks."""
OLD = '''        sha256sum -z -- "$path"
    done | base64 -w0)'''
NEW = '''        printf '%s\\0' "$path"
    done | xargs -0 -r sha256sum -z -- | base64 -w0)'''

def patch_support(source):
    if source.count(OLD) != 1:
        raise RuntimeError('Official inventory helper changed; review required')
    return source.replace(OLD, NEW)

def install():
    from r2t.go import execution
    execution._SUPPORT = patch_support(execution._SUPPORT)
