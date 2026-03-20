package setup

// Sync embedded plugin copies from the source of truth (plugin/ directory).
// Claude Code is installed via marketplace so it needs no embedding.
// Run: go generate ./internal/setup/
//go:generate sh -c "rm -rf plugins/opencode && mkdir -p plugins/opencode && cp ../../plugin/opencode/engram.ts plugins/opencode/"
//go:generate sh -c "rm -rf plugins/cursor && mkdir -p plugins/cursor/scripts plugins/cursor/rules && cp ../../plugin/cursor/scripts/*.py plugins/cursor/scripts/ && cp ../../plugin/cursor/rules/*.mdc plugins/cursor/rules/"
