---
name: require-aws-profile-apro-sandbox
enabled: true
event: bash
conditions:
  - field: command
    operator: regex_match
    pattern: \baws\s+|AWS_PROFILE=(?!apro-sandbox)
---

**AWS Profile Required: apro-sandbox**

All AWS CLI commands in this project MUST use `AWS_PROFILE=apro-sandbox`.

**Correct usage:**
```bash
AWS_PROFILE=apro-sandbox aws <command>
```

Please prefix your AWS command with `AWS_PROFILE=apro-sandbox`.
