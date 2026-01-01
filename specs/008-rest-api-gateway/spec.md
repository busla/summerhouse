# Feature Specification: REST API Gateway Migration

**Feature Branch**: `008-rest-api-gateway`
**Created**: 2025-12-31
**Status**: Draft
**Input**: User description: "convert the infrastructure/modules/gateway-v2 to API Gateway REST API"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Infrastructure Team Deploys REST API Gateway (Priority: P1)

As an infrastructure engineer, I need to deploy the booking API using AWS API Gateway REST API instead of HTTP API, so that I can leverage REST API-specific features like request validation, API keys, and usage plans.

**Why this priority**: This is the core functionality - without a working REST API deployment, the entire feature is incomplete. The platform cannot serve API requests without this.

**Independent Test**: Can be fully tested by running `task tf:plan:dev` followed by `task tf:apply:dev` and verifying that API endpoints respond correctly through the REST API URL.

**Acceptance Scenarios**:

1. **Given** the infrastructure module is configured, **When** `task tf:apply:dev` is executed, **Then** API Gateway REST API is created with all defined endpoints
2. **Given** the REST API is deployed, **When** an authenticated request is made to any endpoint, **Then** the Lambda function is invoked and returns the expected response
3. **Given** the REST API is deployed, **When** the API URL is accessed, **Then** it uses the REST API endpoint format (e.g., `https://{api-id}.execute-api.{region}.amazonaws.com/{stage}`)

---

### User Story 2 - OpenAPI-Driven REST API Configuration (Priority: P1)

As an infrastructure engineer, I need the REST API configuration to be driven by the existing OpenAPI specification, so that route definitions remain in sync with the FastAPI backend automatically.

**Why this priority**: The existing system uses OpenAPI generation from FastAPI decorators. Maintaining this pattern ensures consistency and reduces manual configuration drift.

**Independent Test**: Can be verified by modifying a FastAPI route decorator, regenerating the OpenAPI spec, and confirming the REST API updates on next `tf:apply`.

**Acceptance Scenarios**:

1. **Given** the OpenAPI spec is generated from FastAPI, **When** Terraform applies, **Then** REST API routes match the OpenAPI definition exactly
2. **Given** a new endpoint is added to FastAPI with JWT auth, **When** OpenAPI is regenerated and Terraform applies, **Then** the new endpoint appears in REST API with Cognito authorizer attached
3. **Given** the OpenAPI spec includes CORS configuration, **When** Terraform applies, **Then** REST API responds correctly to preflight OPTIONS requests

---

### User Story 3 - Cognito JWT Authorization on Protected Endpoints (Priority: P1)

As a platform operator, I need protected API endpoints to validate Cognito JWT tokens, so that only authenticated users can access secured resources.

**Why this priority**: Security is non-negotiable. The booking platform handles personal data and reservations that must be protected.

**Independent Test**: Can be verified by making requests to protected endpoints with and without valid JWT tokens and confirming appropriate 401/403 responses for unauthorized requests.

**Acceptance Scenarios**:

1. **Given** an endpoint marked as protected in OpenAPI, **When** a request is made without Authorization header, **Then** REST API returns 401 Unauthorized
2. **Given** an endpoint marked as protected in OpenAPI, **When** a request is made with a valid Cognito JWT, **Then** the request proceeds to Lambda
3. **Given** an endpoint marked as protected in OpenAPI, **When** a request is made with an expired JWT, **Then** REST API returns 401 Unauthorized

---

### User Story 4 - Existing Infrastructure Integration (Priority: P2)

As an infrastructure engineer, I need the REST API module to maintain the same interface (inputs/outputs) as the current HTTP API module, so that the migration requires minimal changes to the root Terraform configuration.

**Why this priority**: Reducing blast radius of the change minimizes risk and makes rollback easier if issues arise.

**Independent Test**: Can be verified by comparing module inputs/outputs before and after migration and confirming root module requires no changes (or minimal, documented changes).

**Acceptance Scenarios**:

1. **Given** the module interface is unchanged, **When** the root Terraform configuration references the new module, **Then** no input variable changes are required
2. **Given** the module outputs are compatible, **When** other modules consume gateway outputs (e.g., `api_gateway_url`), **Then** they continue to work without modification
3. **Given** the Lambda function configuration is unchanged, **When** REST API invokes Lambda, **Then** the same handler and environment variables are used

---

### User Story 5 - CloudWatch Logging and Monitoring (Priority: P2)

As a platform operator, I need REST API access logs in CloudWatch, so that I can monitor API usage, debug issues, and maintain audit trails.

**Why this priority**: Operational visibility is essential for production systems but not required for initial functionality.

**Independent Test**: Can be verified by making API requests and confirming log entries appear in the designated CloudWatch log group.

**Acceptance Scenarios**:

1. **Given** REST API is deployed with logging enabled, **When** a request is made, **Then** request details appear in CloudWatch logs
2. **Given** CloudWatch logging is configured, **When** viewing logs, **Then** request ID, method, path, status, and latency are logged
3. **Given** log retention is configured, **When** logs older than retention period exist, **Then** they are automatically deleted

---

### Edge Cases

- What happens when the OpenAPI spec contains invalid syntax? The Terraform plan should fail with a clear error message.
- How does the system handle Lambda cold starts? REST API timeout must accommodate Lambda cold start time.
- What happens when Cognito user pool is unavailable? REST API Cognito authorizer returns 401 Unauthorized (native behavior, not customizable without Lambda authorizer).
- How does the system handle concurrent deployments? Terraform state locking prevents conflicts.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST deploy AWS API Gateway REST API (not HTTP API) using Terraform
- **FR-002**: System MUST integrate with existing Lambda function using `aws_proxy` integration type (REST API lowercase format)
- **FR-003**: System MUST support OpenAPI-driven route configuration via the `body` parameter
- **FR-004**: System MUST configure Cognito JWT authorizer for protected endpoints
- **FR-005**: System MUST enable CloudWatch access logging with configurable retention
- **FR-006**: System MUST support CORS preflight requests via OpenAPI configuration
- **FR-007**: System MUST maintain the Lambda layer pattern for dependencies (no changes to Lambda packaging)
- **FR-008**: System MUST use CloudPosse label module for consistent naming and tagging
- **FR-009**: System MUST output API Gateway URL, ID, ARN, and OAuth2 callback URL
- **FR-010**: System MUST use terraform-aws-modules where applicable (Lambda module remains unchanged)
- **FR-011**: Module MUST be fully declarative - no manual steps required before `tf:apply`

### Key Entities

- **REST API**: The API Gateway REST API resource that routes requests to Lambda
- **Stage**: Deployment stage (e.g., "prod" or "v1") that controls API versioning and settings
- **Authorizer**: Cognito JWT authorizer that validates tokens on protected endpoints
- **Integration**: AWS_PROXY integration connecting routes to Lambda function
- **Log Group**: CloudWatch log group for API access logs

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All existing API endpoints remain accessible after migration (100% endpoint parity)
- **SC-002**: Deployment completes successfully via `task tf:apply:dev` without manual intervention
- **SC-003**: Protected endpoints correctly reject unauthorized requests (100% of unauthenticated requests return 401)
- **SC-004**: API response latency remains within 3 seconds for typical requests (matching current performance)
- **SC-005**: CloudWatch logs capture all API requests with request/response metadata
- **SC-006**: Module interface changes are documented if any inputs/outputs differ from current module

## Assumptions

- The OpenAPI generation script (`api.scripts.generate_openapi`) will be updated to produce REST API-compatible OpenAPI extensions (e.g., `x-amazon-apigateway-integration` format differences)
- Cognito User Pool and Client IDs remain unchanged and compatible with REST API authorizer
- Lambda function handler and runtime remain unchanged (Python 3.13, FastAPI via Mangum)
- The frontend URL and CORS origins configuration remain compatible
- Stage name will be fixed as `"api"` across all environments - CloudFront origin path (`/api`) abstracts this from end users

## Constraints

- Must follow CLAUDE.md requirements: terraform-aws-modules where available, CloudPosse labels, Taskfile commands only
- No manual pre-build steps allowed - module must be fully declarative
- Must maintain backward compatibility with existing root module configuration where possible
- Lambda packaging (UV workspace with layer) remains unchanged - only API Gateway resource type changes

## Out of Scope

- API Gateway caching configuration (can be added later)
- API key and usage plan setup (can be added later)
- Custom domain name configuration (can be added later)
- Request/response transformation beyond Lambda proxy integration
- Changes to the Lambda function code or FastAPI application
- Changes to DynamoDB tables or data model
