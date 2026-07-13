# Security Policy

## Supported Versions

Only the latest released version is supported. Please upgrade before reporting an issue.

## Reporting a Vulnerability

If you discover a security vulnerability in pytest-skill-engineering, please **do not open a public issue**. Instead, use GitHub's private vulnerability reporting:

**[Report a vulnerability](https://github.com/sbroenne/pytest-skill-engineering/security/advisories/new)** (Security tab → "Report a vulnerability")

**Please include:**
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested fixes (if available)

We will acknowledge receipt within 48 hours and provide a timeline for a fix.

## Security Considerations

This library makes calls to external LLM APIs and can execute MCP servers and CLI tools. When using pytest-skill-engineering:

- **API Keys**: Never commit API keys to version control. Use environment variables.
- **Sensitive Data**: Be cautious about what content you send to LLM providers for evaluation.
- **Network Security**: LLM API calls are made over HTTPS by default.
- **MCP Servers**: Only run trusted MCP servers — they have access to execute code and tools.
- **CLI Tools**: Test CLI tools in isolated environments when possible.
