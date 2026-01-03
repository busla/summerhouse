# Research: Fix Next.js Routing and WAF 403 Errors

**Feature Branch**: `012-fix-routing-waf`
**Created**: 2026-01-03
**Status**: Complete

## Research Questions

### RQ-001: How should CloudFront Functions handle URL normalization for Next.js static sites?

**Context**: With Next.js `trailingSlash: true`, pages export as `/gallery/index.html`. CloudFront receives requests like `/gallery` (no trailing slash) and `/gallery/` (with trailing slash) but S3 only stores `/gallery/index.html`.

**Finding**: AWS provides an official CloudFront Functions example for exactly this use case.

**Source**: [AWS CloudFront Functions - URL rewrite for single page apps](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/example_cloudfront_functions_url_rewrite_single_page_apps_section.html)

**Recommended Implementation**:

```javascript
async function handler(event) {
    var request = event.request;
    var uri = request.uri;

    // Check whether the URI is missing a file name.
    if (uri.endsWith('/')) {
        request.uri += 'index.html';
    }
    // Check whether the URI is missing a file extension.
    else if (!uri.includes('.')) {
        request.uri += '/index.html';
    }

    return request;
}
```

**Key Behaviors**:
- `/gallery` → `/gallery/index.html` (adds trailing slash + index.html)
- `/gallery/` → `/gallery/index.html` (adds index.html)
- `/gallery/photo.jpg` → `/gallery/photo.jpg` (unchanged - has extension)

**Runtime**: `cloudfront-js-2.0` (latest, required for async functions)

---

### RQ-002: How do we add CloudFront Functions to terraform-aws-modules/cloudfront?

**Context**: The project uses `terraform-aws-modules/cloudfront/aws` version ~> 6.0. Need to understand how to add function associations.

**Finding**: The module has native support via `cloudfront_functions` input and `function_association` in cache behaviors.

**Source**: [terraform-aws-modules/cloudfront README](https://registry.terraform.io/modules/terraform-aws-modules/cloudfront/aws/latest)

**Recommended Implementation**:

```hcl
module "cloudfront" {
  source  = "terraform-aws-modules/cloudfront/aws"
  version = "~> 6.0"

  # ... existing configuration ...

  # Define the function
  cloudfront_functions = {
    url-rewrite = {
      runtime = "cloudfront-js-2.0"
      comment = "Normalize URLs to index.html for Next.js static site"
      code    = file("${path.module}/functions/url-rewrite.js")
      publish = true
    }
  }

  # Associate with default cache behavior
  default_cache_behavior = {
    # ... existing settings ...

    function_association = {
      viewer-request = {
        function_key = "url-rewrite"
      }
    }
  }
}
```

**Key Insights**:
- Function is created by the module (no separate `aws_cloudfront_function` resource needed)
- Use `function_key` to reference module-managed functions
- Event type `viewer-request` processes URLs before S3 lookup
- Function must be `publish = true` to be used in production

---

### RQ-003: What's the best pattern for form persistence with sessionStorage in React?

**Context**: The booking page `/book/` has a multi-step form with dates, guest details. Users lose data on browser refresh.

**Finding**: sessionStorage with JSON serialization is the standard approach. Key considerations:
1. **sessionStorage vs localStorage**: sessionStorage clears when tab closes (better for sensitive booking data)
2. **Serialization**: Date objects need special handling (ISO strings)
3. **React integration**: Custom hook with `useEffect` for sync

**Recommended Implementation**:

```typescript
// hooks/useFormPersistence.ts
import { useState, useEffect, useCallback } from 'react'

interface UseFormPersistenceOptions<T> {
  key: string
  initialValue: T
  serialize?: (value: T) => string
  deserialize?: (stored: string) => T
}

export function useFormPersistence<T>({
  key,
  initialValue,
  serialize = JSON.stringify,
  deserialize = JSON.parse,
}: UseFormPersistenceOptions<T>) {
  // Initialize from sessionStorage on mount
  const [value, setValue] = useState<T>(() => {
    if (typeof window === 'undefined') return initialValue

    const stored = sessionStorage.getItem(key)
    if (!stored) return initialValue

    try {
      return deserialize(stored)
    } catch {
      return initialValue
    }
  })

  // Sync to sessionStorage on change
  useEffect(() => {
    sessionStorage.setItem(key, serialize(value))
  }, [key, value, serialize])

  // Clear function for cleanup after booking
  const clear = useCallback(() => {
    sessionStorage.removeItem(key)
    setValue(initialValue)
  }, [key, initialValue])

  return [value, setValue, clear] as const
}
```

**Key Design Decisions**:
- Lazy initialization in `useState` prevents SSR issues
- Custom serializer/deserializer for Date handling
- `clear()` function for post-booking cleanup
- Storage key scoped per form to avoid collisions

**Date Handling**:

```typescript
// For DateRange with Date objects
const serializeDates = (range: DateRange | undefined) =>
  JSON.stringify(range, (_, v) => v instanceof Date ? v.toISOString() : v)

const deserializeDates = (stored: string) =>
  JSON.parse(stored, (_, v) =>
    typeof v === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(v) ? new Date(v) : v
  )
```

---

### RQ-004: How should active navigation state work with trailing slashes?

**Context**: Navigation.tsx needs to highlight the current page. With `trailingSlash: true`, URLs may be `/gallery` or `/gallery/` depending on how the user arrived.

**Finding**: Next.js `usePathname()` returns the path with or without trailing slash depending on the current URL. Need to normalize for comparison.

**Recommended Implementation**:

```typescript
// In Navigation.tsx
import { usePathname } from 'next/navigation'

const pathname = usePathname()

// Normalize both link href and pathname for comparison
const normalizePathname = (path: string) =>
  path === '/' ? path : path.replace(/\/$/, '')

const isActive = (href: string) =>
  normalizePathname(pathname) === normalizePathname(href)
```

**Alternative**: Use the link href with trailing slash consistently and compare directly.

---

### RQ-005: Why does S3 with OAC return 403 instead of 404 for missing objects?

**Context**: Users see 403 when accessing routes without index.html resolution, which looks like a WAF block rather than a missing file.

**Finding**: This is intentional security behavior. S3 with Origin Access Control (OAC) returns 403 for any object access error to prevent information disclosure about bucket contents.

**Source**: AWS S3 security best practices

**Impact**: With the CloudFront Function adding `/index.html`, this becomes a non-issue for valid routes. For truly invalid routes:
- `/nonexistent/` → `/nonexistent/index.html` → S3 returns 403 → CloudFront shows 403.html

**Recommendation**: This is acceptable because:
1. Valid routes will now work with the URL rewrite function
2. Custom 403.html page exists for genuine errors (WAF blocks or truly invalid routes)
3. Distinguishing 403 (blocked) from 404 (not found) would require S3 ListBucket permission, which is a security risk

---

## Unknowns Resolved

| ID | Unknown | Resolution |
|----|---------|------------|
| U-001 | CloudFront Function syntax for URL rewriting | Official AWS example available, uses async handler |
| U-002 | terraform-aws-modules/cloudfront function support | Native support via `cloudfront_functions` + `function_association` |
| U-003 | sessionStorage API for form persistence | Standard browser API with JSON serialization |
| U-004 | Date serialization in sessionStorage | Use ISO strings via custom serializer/deserializer |
| U-005 | Active state detection with trailing slashes | Normalize both paths by stripping trailing slashes |

## Risks Identified

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| CloudFront Function deployment delay | Low | Low | Functions deploy in seconds; use `wait_for_deployment = false` |
| sessionStorage unavailable (private browsing) | Low | Low | Graceful degradation - form works, just doesn't persist |
| Breaking existing API routes | Low | High | Function only affects paths without extensions; `/api/*` has `.` in paths |

## Next Steps

1. **Phase 1**: Write data-model.md (form state types)
2. **Phase 1**: Write quickstart.md (deployment/testing guide)
3. **Phase 2**: Generate tasks.md via `/speckit.tasks`
