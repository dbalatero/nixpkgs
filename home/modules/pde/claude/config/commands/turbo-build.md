# Turbo Build Helper

Help users build specific packages efficiently in Turborepo monorepos.

## Usage

- `/turbo-build @scope/package` - Build single package
- `/turbo-build @scope/package...` - Build package + dependencies
- `/turbo-build --affected` - Build only changed packages

## Key Patterns

- **Never run `yarn build` or `npm run build` at root** - Too slow, builds everything
- **Use `--filter` for targeted builds** - Only build what you need
- **Use `...` suffix to include dependencies** - e.g., `--filter=@scope/pkg...`
- **Check turbo cache hits** - Look for "FULL TURBO" or cache hit messages in output

## Commands

### Build Single Package
```bash
yarn turbo run build --filter=@scope/package-name
```

### Build Package + All Dependencies
```bash
yarn turbo run build --filter=@scope/package-name...
```

### Build Only Affected Packages
```bash
yarn turbo run build --affected
```

### Build Multiple Specific Packages
```bash
yarn turbo run build --filter=@scope/pkg1 --filter=@scope/pkg2
```

### Dry Run (See What Would Build)
```bash
yarn turbo run build --filter=@scope/package-name --dry-run
```

## Troubleshooting

### "Module not found" Errors
Usually means a dependency wasn't built. Use the `...` suffix:
```bash
yarn turbo run build --filter=@scope/package...
```

### Stale Cache
Clear turbo cache and rebuild:
```bash
yarn turbo run build --filter=@scope/package --force
```

### Find Package Name
Look in the package's `package.json` for the `name` field, or:
```bash
# List all packages
cat turbo.json
# Or check package directories
ls packages/
```

## Tips

1. **Start with the package you're working on** - Only build more if you get import errors
2. **Use `--dry-run` first** - See what would be built without actually building
3. **Watch for cache hits** - If you see "FULL TURBO", the cache is working
4. **Check `turbo.json`** - Understand the dependency graph and pipeline
