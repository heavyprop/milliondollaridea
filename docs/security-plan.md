# Anti-scraping plan for LLM training

Status: planning only. This revision changes only this document and replaces the earlier high-security proposal.

## Goal

Create a normal discussion website for people who do not want their posts collected in bulk for LLM training. Focus on crawler opt-outs, account-based reading, and detecting bulk collection. The site is not intended as a vault for confidential information.

We cannot reliably tell whether a person downloading posts intends to train a model. Enforce limits against bulk collection regardless of the claimed purpose. Anyone who can read a post can still copy it; this plan reduces scraping rather than guaranteeing prevention.

## Recommended first version

1. Let people sign up normally, with email verification and a signup bot check.
2. Keep full posts and comments behind login, as the current site largely does.
3. Let signed-in users read normally without clicking an extra reveal button on every post.
4. Publish crawler opt-outs for training and dataset collection.
5. Limit rapid or sustained bulk reading, search, and account creation.
6. Challenge suspicious activity; established accounts encounter fewer challenges.
7. Retain normal website security: HTTPS, secure sessions, safe production settings, and protected backups.

No invitation requirement, routine manual approval, identity documents, private audiences, or per-post encryption is needed for this scope.

## Public versus member content

Public pages can show the landing page, community descriptions, and optionally post titles. Full descriptions and comments require login. Optional public teasers should be short, fixed, and author-approved; anything public can be collected.

Do not expose full member content through anonymous search, HTML metadata, feeds, JSON endpoints, notifications, or shared caches. Apply login checks on the server, not just through hidden buttons.

Keep ordinary search engines able to discover public pages. They will not index the full member-only discussion. Do not give crawlers a special bypass to content that visitors cannot read.

## Crawler opt-outs

Publish a public `/robots.txt` with explicit rules for current training crawlers and general-purpose dataset collectors. Verify the provider list before implementation and periodically afterward; providers change their crawler names and policies.

For example, Anthropic documents `ClaudeBot` for model-development crawling separately from its search and user-requested retrieval bots. Its training crawler can be disallowed without automatically disallowing those other bots. [Anthropic crawler documentation](https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler)

Common Crawl publishes the following opt-out for its publicly available crawl dataset. Blocking dataset collectors matters because content can reach model developers indirectly. [Common Crawl documentation](https://commoncrawl.org/ccbot)

```text
# Illustrative subset, not a complete crawler policy.
User-agent: ClaudeBot
Disallow: /

User-agent: CCBot
Disallow: /
```

Keep training, search indexing, and user-requested retrieval as separate policy decisions. Do not assume a generic “block AI” switch makes those distinctions.

Robots rules depend on crawler cooperation. Add server/CDN blocking for identified unwanted bots where useful, but do not trust a user-agent string as proof of identity. A scraper can identify itself as a browser.

State the site's preference against bulk collection for model training in its content-use policy. Policy text communicates the rule; it does not technically prevent copying or remove material already collected.

## Lightweight trust

Use three simple states instead of an elaborate points economy:

| State | How it works |
| --- | --- |
| New | Verified account; ordinary reading allowed, with earlier checks if activity becomes unusually fast |
| Established | Account used normally across multiple days; fewer routine bot checks |
| Flagged | Strong signs of bulk collection or compromise; temporary cooldown, verification, or review |

Account age and a history of normal server-observed use can support established status. Helpful posting and commenting can contribute modestly, but are not required. Quiet readers should not have to post to earn access.

Do not award access directly for numbers of posts, likes, mouse movements, or browser-reported reading seconds: these can be manufactured. Keep any contribution credit capped. A trusted account still has rate limits and can be flagged.

CAPTCHA completion clears a temporary check. It does not add permanent trust or refill a download allowance. Repeatedly solving CAPTCHAs must not enable an unlimited scrape.

## Reading limits and challenges

Start with generous limits intended to catch harvesting, not ordinary reading. Illustrative pilot settings:

- At most 20 posts per list page and 20 comments per comment page.
- Challenge after more than 30 distinct thread opens in five minutes.
- Temporarily cool down an account collecting more than 300 distinct threads in a rolling day.
- Rate-limit search separately, initially around 20 requests per minute per account.
- Bound response sizes and comment-page collection too; one huge thread must not become an unlimited export.

These numbers are starting hypotheses, not security guarantees. Tune them using actual reader activity and false-positive reports. A slow scraper can stay below every short-term threshold, so also look for sustained collection across days and coordinated accounts.

Combine account limits with coarse session/network signals. Switching IP, logging out, or opening another tab must not reset an account's counters. Shared IPs and VPN use alone are not grounds for a ban. Use atomic shared counters across server workers.

Response sequence: normal access → suspicious activity check → temporary cooldown → review or suspension for repeated clear abuse. Passing a challenge does not override an exhausted collection limit. Validate challenges on the server and prevent token replay. Offer an accessible alternative when someone cannot complete a challenge. [OWASP anti-automation guidance](https://cheatsheetseries.owasp.org/cheatsheets/Bot_Management_and_Anti-Automation_Cheat_Sheet.html)

Store minimal operational data, such as request counts, resource identifiers, timestamps, and decision reasons. Start with short retention, for example 14 days, and avoid invasive fingerprinting or logging post bodies.

## Encryption and the reveal button

Do not encrypt 50% of descriptions. The visible half still provides usable training material, and a permitted reader or automated browser can collect anything eventually revealed.

For this goal, ordinary storage and backup encryption plus HTTPS are appropriate. Application-level field encryption and end-to-end encryption add complexity without stopping a logged-in scraper from collecting rendered text. Keep server-side search and recommendations working normally.

Skip the reveal button for the first version. If later evidence justifies one, use it for suspicious sessions: withhold the body until the server checks the request. Merely hiding already-delivered text with CSS offers no protection.

Do not add scrambled text, disabled copying, text rendered as images, or fake encryption indicators. They add friction without reliably preventing collection.

## Repository implementation plan

1. **Baseline:** harden production settings in `config/settings/`, retain Django escaping/CSRF protections, and protect sessions and backups. This remains necessary for any ordinary website.
2. **Signup:** add email verification and signup/login abuse controls in `apps/accounts/views.py`; normal users should not wait for manual approval.
3. **Crawler policy:** add `/robots.txt` and a clear content-use statement. Keep the robots file publicly accessible.
4. **Bound collection:** paginate the home feed, subject pages, search results, and comments in `apps/feed/views.py and apps/search/views.py` and `apps/discussions/views/`. Add shared per-account and coarse network limits.
5. **Trust and challenges:** add a small account-status model and one reusable request-checking service. Apply it to all routes returning posts/comments, including future APIs and fragments.
6. **Observe and tune:** inspect aggregate collection patterns, challenge frequency, false blocks, and slow multi-account harvesting before adding more controls.

The current member-only previews and description search can remain. They need the same collection controls as detail pages, because a scraper can gather text from lists and search too. Never expose those member previews anonymously by accident.

Keep post content out of external model-training pipelines, session-replay services, and unnecessary third-party integrations. Review any future external AI integration against the site's stated purpose.

## Checks before launch

- Logged-out requests cannot obtain full posts/comments through alternate routes or caches.
- List, search, and comment endpoints cannot return an unbounded collection.
- Parallel requests and new sessions cannot bypass account limits.
- CAPTCHA replay fails, and successful CAPTCHA does not reset quotas.
- Established users can read normally; spam contributions cannot buy unlimited access.
- Crawler rules match current provider documentation and do not accidentally block intended public search discovery.
- A controlled scraper hits measurable limits; ordinary browsing rarely triggers a challenge.

Suggested public wording: “A community that opts out of AI-training crawlers and limits bulk content collection.” Do not promise that posts can never reach a training dataset.
