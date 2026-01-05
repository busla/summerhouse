---
name: cloudwatch-logs-mcp
enabled: true
event: prompt
conditions:
  - field: user_prompt
    operator: regex_match
    pattern: (cloudwatch|log\s*(group|stream|insight)|check.*logs?|view.*logs?|get.*logs?|analyze.*logs?|debug.*logs?)
action: warn
---

## CloudWatch Logs Reminder

When investigating CloudWatch logs, **ALWAYS**:

1. **Use the CloudWatch MCP server** (`mcp__awslabs_cloudwatch-mcp-server__*` tools):
   - `describe_log_groups` - Discover available log groups
   - `execute_log_insights_query` - Query logs with CloudWatch Insights
   - `analyze_log_group` - Analyze for anomalies and patterns
   - `get_logs_insight_query_results` - Retrieve query results

2. **Check the LATEST logs** by:
   - Using the correct log group:
     - Fastapi lambda: `/aws/lambda/booking-dev-api`
     - ApiGateway: `/aws/apigateway/booking-dev-api`
   - Using recent timestamps (last 5-10 minutes depending on context)
   - Sorting by timestamp descending when relevant
   - Including `| sort @timestamp desc | limit 50` in Insights queries

3. **Example query for recent logs**:
   ```
   fields @timestamp, @message
   | filter @message like /error|Error|ERROR/
   | sort @timestamp desc
   | limit 100
   ```

**Do NOT** rely on cached data or assumptions about log content - always fetch fresh data!
