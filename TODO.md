- [x] Respect .gitignore via ToolPolicy so Koda can not read .env etc.

- [ ] Scrolling in TUI is not as smooth as one wants it
- [ ] Scrolling by grabbing the scrollbar
- [ ] Highlight text in the TUI
- [ ] KODAs context runs out rapidly. Investigate
- [ ] Add tests to verify tools. 1. schema generation. 2. sandbox enforcement. 3. tool execution returns ToolResult with correct call_id. 4 Errors are correctly formatted. Definitions should work across providers.
- [ ] Investigate: Keep ToolDefinition, but enhance it to include a JSON schema derived from pydantic so providers don't each implement their own conversion.
