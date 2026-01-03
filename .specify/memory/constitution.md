<!--
╔══════════════════════════════════════════════════════════════════════════════╗
║                           SYNC IMPACT REPORT                                  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ Version Change: 1.2.0 → 1.3.0 (shadcn + OpenAPI client generation added)     ║
║                                                                              ║
║ Modified Principles:                                                         ║
║   - VI. Technology Stack > UI Component Development: Added shadcn priority   ║
║   - VI. Technology Stack: Added new "Frontend API Integration" subsection    ║
║                                                                              ║
║ Added Sections:                                                              ║
║   - VI. Technology Stack > UI Component Development                          ║
║     - MUST prefer shadcn/ui components over custom implementations           ║
║     - MUST research shadcn catalogue before writing custom components        ║
║   - VI. Technology Stack > Frontend API Integration (NEW)                    ║
║     - MUST generate HTTP clients from FastAPI OpenAPI schema                 ║
║     - MUST NOT write custom fetch/axios calls for API endpoints              ║
║     - MUST regenerate client when OpenAPI spec changes                       ║
║                                                                              ║
║ Removed Sections:                                                            ║
║   - None                                                                     ║
║                                                                              ║
║ Templates Status:                                                            ║
║   - .specify/templates/plan-template.md        ✅ Compatible (Constitution   ║
║     Check section will enforce new principles during planning)               ║
║   - .specify/templates/spec-template.md        ✅ Compatible (no changes)    ║
║   - .specify/templates/tasks-template.md       ✅ Compatible (no changes)    ║
║                                                                              ║
║ Deferred TODOs:                                                              ║
║   - None                                                                     ║
╚══════════════════════════════════════════════════════════════════════════════╝
-->

# Booking Constitution

## Core Principles

### I. Test-First Development (NON-NEGOTIABLE)

All features MUST follow Test-Driven Development (TDD):

- Tests MUST be written before implementation code
- Tests MUST fail before implementation begins (Red phase)
- Implementation MUST only satisfy failing tests (Green phase)
- Refactoring MUST NOT change test outcomes (Refactor phase)
- No feature is considered complete until tests pass

**Rationale**: TDD ensures correctness by design, prevents regression, and produces
naturally testable architecture. Skipping this principle creates technical debt that
compounds over time.

### II. Simplicity & YAGNI

Code MUST be the simplest solution that satisfies current requirements:

- MUST NOT add features "for future use" without explicit specification
- MUST prefer direct solutions over abstractions until patterns emerge (Rule of Three)
- MUST delete unused code rather than commenting it out
- SHOULD choose boring technology over novel solutions unless requirements demand otherwise
- MUST justify any abstraction layer with concrete current use cases

**Rationale**: Premature complexity is the enemy of delivery. Simple code is easier to
understand, test, modify, and delete.

### III. Type Safety

All code MUST leverage the type system to prevent errors at compile/lint time:

- MUST use strict type checking (e.g., `strict: true` in TypeScript, type hints in Python)
- MUST NOT use `any`, `unknown` escape hatches without documented justification
- MUST validate external inputs at system boundaries and convert to typed representations
- MUST define explicit types for function parameters and return values
- SHOULD use discriminated unions/enums over stringly-typed values

**Rationale**: The type system catches errors before runtime, serves as executable
documentation, and enables confident refactoring.

### IV. Observability

All systems MUST be observable in development and production:

- MUST use structured logging (JSON format) with consistent field names
- MUST include correlation IDs for request tracing across boundaries
- MUST log all error conditions with sufficient context for debugging
- MUST expose health check endpoints for any network service
- SHOULD instrument critical paths with timing metrics
- MUST NOT log sensitive data (credentials, PII, tokens)

**Rationale**: You cannot fix what you cannot see. Observability transforms debugging
from guesswork into systematic investigation.

### V. Incremental Delivery

Features MUST be delivered in small, independently valuable increments:

- MUST break features into user stories that can be tested independently
- MUST ensure each increment is deployable without breaking existing functionality
- MUST prioritize working software over comprehensive features
- SHOULD target increments that can be completed within one development session
- MUST NOT block delivery waiting for "complete" implementations

**Rationale**: Small increments reduce risk, enable faster feedback, and maintain
momentum. Shipping something useful beats planning something perfect.

### VI. Technology Stack (NON-NEGOTIABLE)

All development MUST use the prescribed technology stack for consistency and
maintainability across the project:

**Frontend Agent Development**

- MUST use Vercel AI SDK v6 (ai-sdk) for AI/LLM integration
- MUST use ai-elements package for agent UI components
- MUST NOT use alternative AI SDK libraries without documented justification and
  amendment to this constitution

**UI Component Development**

- MUST prefer shadcn/ui components over custom implementations for all standard UI elements
- MUST research the shadcn/ui catalogue before planning any UI component implementation
- MUST research the ai-elements catalogue for agent-specific UI components
- MUST document which shadcn/ui or ai-elements components were considered and their
  applicability
- MUST use existing shadcn/ui or ai-elements components when they meet requirements
  (even partially)
- MUST justify with documented rationale any decision to implement custom components
  when existing libraries lack suitable options
- SHOULD extend or compose existing components rather than building from scratch
- MUST NOT implement custom UI components that duplicate shadcn/ui or ai-elements
  functionality

**Frontend API Integration**

- MUST generate TypeScript HTTP clients from the FastAPI backend OpenAPI schema
- MUST use @hey-api/openapi-ts (or equivalent OpenAPI generator) to generate type-safe
  API clients
- MUST NOT write custom fetch, axios, or other HTTP calls for API endpoints that exist
  in the OpenAPI schema
- MUST regenerate the API client whenever the backend OpenAPI specification changes
- MUST use the generated client's types for all API request/response handling
- SHOULD configure the generated client with interceptors for cross-cutting concerns
  (auth headers, error handling, logging)

**Backend Agent Development**

- MUST use Strands agent framework for all agent backend development
- MUST follow Strands patterns for tool definition, agent orchestration, and
  conversation management
- MUST NOT implement custom agent frameworks when Strands provides the capability

**Infrastructure**

- MUST use the `terraform-aws-agentcore` module located at
  `~/code/apro/agentcore-sandbox/terraform-aws-agentcore` for all AWS infrastructure
- MUST NOT create ad-hoc Terraform resources that duplicate module functionality
- Infrastructure changes MUST be made through the module or by extending it

**Rationale**: A consistent technology stack reduces cognitive load, enables knowledge
sharing, and prevents fragmentation. These specific choices align with the agent-first
architecture and AWS deployment target of the Booking platform. Preferring shadcn/ui
ensures consistent, accessible UI patterns with minimal custom code. Generating API
clients from OpenAPI ensures type safety across the frontend-backend boundary and
eliminates manual synchronization errors.

## Quality Standards

Code quality gates that MUST pass before any merge:

- All tests pass (unit, integration, contract as applicable)
- Type checking passes with no errors
- Linting passes with no errors or warnings
- No decrease in test coverage without justification
- Documentation updated for any public API changes

## Development Workflow

Standard workflow enforcing constitution compliance:

1. **Specification**: Define user stories with acceptance criteria (spec.md)
2. **Planning**: Design approach with constitution check (plan.md)
3. **Test Writing**: Write failing tests for acceptance criteria
4. **Implementation**: Write minimal code to pass tests
5. **Refactoring**: Improve code while maintaining passing tests
6. **Review**: Verify compliance with all principles before merge

## Governance

This constitution is the supreme authority for development practices in Booking:

- **Supremacy**: Constitution principles override all other guidelines, preferences,
  or conventions when in conflict
- **Amendments**: Changes require documented rationale, review, and version increment
- **Versioning**: Follows semantic versioning (MAJOR.MINOR.PATCH)
  - MAJOR: Principle removal or incompatible redefinition
  - MINOR: New principle or section added
  - PATCH: Clarifications or wording improvements
- **Compliance**: All code reviews MUST verify constitution compliance
- **Exceptions**: Any principle violation MUST be documented with justification in the
  Complexity Tracking section of the relevant plan.md

**Version**: 1.3.0 | **Ratified**: 2025-12-27 | **Last Amended**: 2026-01-03
