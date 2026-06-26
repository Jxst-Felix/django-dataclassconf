# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

...

## [0.1.0] - 2026-05-30

### Added

- Added `BaseConfig` abstract class for as base class for configuration dataclasses
- Added Configuration loader that loads the settings into configuration dataclasses

---

## [0.2.0] - 2026-06-11

### Added

- Added `Importable` type annotation for settings that can be imported

### Changed

- `update` method of `BaseConfig` get extra steps in parsing from settings to dataclass configuration to ensure that `Importable` fields are wrapped properly and ready to use

---

## [0.3.0] - 2026-06-26

### Added

- Added the following base class `FieldValue`, `FieldGeneric`, `Field` to enable Library users in creating their own fields with their custom validators

### Changed

- `update` method of `BaseConfig` get extra steps in parsing from settings to dataclass configuration to ensure that fields are wrapped properly with their corresponding `FieldValue` subclasses and ready to use

---
