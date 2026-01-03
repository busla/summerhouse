# Quickstart: Fix Next.js Routing and WAF 403 Errors

**Feature Branch**: `012-fix-routing-waf`
**Created**: 2026-01-03
**Time to Complete**: ~30 minutes (with existing dev environment)

## Prerequisites

- Node.js 18+ and Yarn Berry
- Terraform >= 1.5.0
- AWS CLI configured with appropriate credentials
- Access to dev environment (whitelisted IP for WAF)

## Quick Verification (Before Changes)

Verify the current issues exist:

```bash
# 1. Start local dev server
task frontend:dev

# 2. In browser, click navbar links and note:
#    - URLs are /gallery, /book (no trailing slash)
#    - Browser refresh on these URLs works locally

# 3. Deploy current version and test CloudFront
task tf:apply:dev

# 4. Access via CloudFront URL and note:
#    - /gallery/ returns 403 (this is the bug)
#    - Navbar links go to /gallery (no trailing slash)
```

## Implementation Steps

### Step 1: Fix Navigation Links (5 min)

Update `frontend/src/components/layout/Navigation.tsx`:

```typescript
// Change all href values to include trailing slashes
const defaultLinks: NavLink[] = [
  { label: 'Home', href: '/' },
  { label: 'Gallery', href: '/gallery/' },    // Added /
  { label: 'Location', href: '/location/' },  // Added /
  { label: 'Book', href: '/book/' },          // Added /
  { label: 'Agent', href: '/agent/' },        // Added /
]
```

### Step 2: Add CloudFront Function (10 min)

Create `infrastructure/modules/static-website/functions/url-rewrite.js`:

```javascript
async function handler(event) {
    var request = event.request;
    var uri = request.uri;

    // Append index.html for directory-style URLs
    if (uri.endsWith('/')) {
        request.uri += 'index.html';
    } else if (!uri.includes('.')) {
        request.uri += '/index.html';
    }

    return request;
}
```

Update `infrastructure/modules/static-website/main.tf` to add the function:

```hcl
module "cloudfront" {
  # ... existing config ...

  cloudfront_functions = {
    url-rewrite = {
      runtime = "cloudfront-js-2.0"
      comment = "Normalize URLs to index.html for Next.js static site"
      code    = file("${path.module}/functions/url-rewrite.js")
      publish = true
    }
  }

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

### Step 3: Add Form Persistence Hook (10 min)

Create `frontend/src/hooks/useFormPersistence.ts`:

```typescript
import { useState, useEffect, useCallback } from 'react'

const STORAGE_KEY = 'booking-form-state'

export function useFormPersistence<T>(initialValue: T) {
  const [value, setValue] = useState<T>(() => {
    if (typeof window === 'undefined') return initialValue
    const stored = sessionStorage.getItem(STORAGE_KEY)
    if (!stored) return initialValue
    try {
      return JSON.parse(stored) as T
    } catch {
      return initialValue
    }
  })

  useEffect(() => {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(value))
  }, [value])

  const clear = useCallback(() => {
    sessionStorage.removeItem(STORAGE_KEY)
    setValue(initialValue)
  }, [initialValue])

  return [value, setValue, clear] as const
}
```

Update `frontend/src/app/book/page.tsx` to use the hook (see implementation tasks for details).

### Step 4: Deploy and Test

```bash
# Run E2E tests locally first
task frontend:test

# Deploy infrastructure + frontend
task tf:apply:dev

# Test via CloudFront
# 1. Visit https://<cloudfront-domain>/gallery/ - should load
# 2. Visit https://<cloudfront-domain>/gallery - should redirect and load
# 3. Click navbar links - should work without 403
# 4. Enter booking form data, refresh - should persist
```

## Verification Checklist

- [ ] All navbar links have trailing slashes in source
- [ ] CloudFront Function deployed and associated with default behavior
- [ ] `/gallery/` loads without 403
- [ ] `/gallery` (no slash) loads without 403
- [ ] Clicking Gallery link in navbar works
- [ ] Browser refresh on `/book/` preserves form data
- [ ] Completing a booking clears persisted form data
- [ ] 404 page shows for truly non-existent routes like `/nonexistent/`

## Troubleshooting

### Still Getting 403 After Deployment

1. **CloudFront invalidation**: Wait 1-2 minutes or run:
   ```bash
   aws cloudfront create-invalidation --distribution-id <ID> --paths "/*"
   ```

2. **Function not associated**: Check Terraform state:
   ```bash
   task tf:output:dev
   # Verify cloudfront_function_arn is present
   ```

3. **WAF blocking**: Verify your IP is whitelisted in `terraform.tfvars.json`

### Form Not Persisting

1. **Private browsing**: sessionStorage may be disabled
2. **Check console**: Look for JSON parse errors
3. **Verify hook usage**: Ensure `useFormPersistence` is called at page level

### Active State Not Highlighting

1. **Path comparison**: Ensure `normalizePathname()` strips trailing slashes
2. **Check pathname**: Log `usePathname()` output in Navigation component

## Rollback

If issues occur, revert the CloudFront Function:

```bash
# Remove function_association from main.tf, then:
task tf:apply:dev
```

The frontend changes are purely cosmetic and won't cause errors - they can be reverted via git.
