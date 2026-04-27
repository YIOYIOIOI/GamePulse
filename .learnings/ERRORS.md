# Errors

## [ERR-20260428-001] unsafe global translation replacement broke TypeScript

**Logged**: 2026-04-28T03:35+08:00
**Priority**: high
**Status**: fixed
**Area**: frontend

### Summary
A broad string replacement pass for Chinese UI localization replaced substrings inside TypeScript identifiers and keywords, breaking compilation.

### Details
Examples included `finally` becoming `fin全部y`, `isSearching` becoming mixed Chinese identifiers, and type names like `SteamAppSearchResult` being altered. The fix was to immediately restore `frontend/src` from git and switch to targeted UI-only localization.

### Suggested Action
For localization, never perform unbounded global English-to-Chinese replacements over source files. Only replace explicit JSX text nodes, option labels, navigation labels, and dedicated display strings; avoid internal enum values, identifiers, keys, dataKey values, and API payload values.

### Metadata
- Source: error
- Related Files: frontend/src/**/*.tsx, frontend/src/**/*.ts
- Tags: localization, typescript, replacement-safety
