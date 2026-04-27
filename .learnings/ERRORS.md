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

## [ERR-20260428-002] assumed ripgrep was available on Windows
- Context: While checking remaining English UI strings in `D:\codes\AI-Powered-GPI-OSS`, attempted to use `rg`, but this Windows environment did not have ripgrep on PATH.
- Symptom: PowerShell returned `rg: The term 'rg' is not recognized...`.
- Fix: Use PowerShell `Get-ChildItem ... | Select-String` for portable local text scans unless tool availability has been verified.
- Lesson: On this machine, do not assume Unix/dev convenience tools are installed; prefer bundled/known tools or PowerShell-native equivalents.
