/**
 * CloudFront Function: URL Rewrite for Next.js Static Site
 *
 * Normalizes URLs to index.html for Next.js static exports with trailingSlash: true.
 *
 * Behaviors:
 * - /gallery → /gallery/index.html (adds trailing slash + index.html)
 * - /gallery/ → /gallery/index.html (adds index.html)
 * - /gallery/photo.jpg → /gallery/photo.jpg (unchanged - has extension)
 * - / → /index.html (root path)
 *
 * Runtime: cloudfront-js-2.0
 * Event: viewer-request (processes URLs before S3 lookup)
 *
 * Source: AWS CloudFront Functions - URL rewrite for single page apps
 * https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/example_cloudfront_functions_url_rewrite_single_page_apps_section.html
 *
 * Feature: 012-fix-routing-waf (T011)
 */
async function handler(event) {
  var request = event.request;
  var uri = request.uri;

  // Check whether the URI is missing a file name (ends with /)
  if (uri.endsWith('/')) {
    request.uri += 'index.html';
  }
  // Check whether the URI is missing a file extension (no . after last /)
  else if (!uri.includes('.')) {
    request.uri += '/index.html';
  }

  return request;
}
