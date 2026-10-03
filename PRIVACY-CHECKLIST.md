# Privacy & Security Checklist for GitHub Repositories

**BEFORE PUSHING TO GITHUB** - Verify all items below to keep secrets out of repositories.

---

## 🔒 Sensitive Information - NEVER Commit

### Credentials & Tokens
- [ ] No API keys, access tokens, or authentication credentials
- [ ] No OAuth2 tokens or refresh tokens
- [ ] No GitHub personal access tokens (PATs)
- [ ] No AWS access keys or secret access keys
- [ ] No database passwords or connection strings
- [ ] No private SSH keys or certificates
- [ ] No service account credentials (Google, Azure, AWS)

### Configuration Files
- [ ] No `.env` files containing secrets (use `.env.example` instead)
- [ ] No `config.local.js`, `config.local.json`, or similar local configs
- [ ] No `secrets.json`, `credentials.json`, or similar files
- [ ] No Docker `.dockercfg` or authentication configs
- [ ] No Kubernetes secrets manifests

### Application Specific
- [ ] No API endpoints with hardcoded credentials
- [ ] No database URIs with passwords
- [ ] No private encryption keys or passphrases
- [ ] No hardcoded email addresses for sensitive accounts
- [ ] No internal IP addresses or hostnames (if sensitive)

### Personal Information (PII)
- [ ] No personally identifiable information (names, emails, phone numbers)
- [ ] No financial information (credit card numbers, bank accounts)
- [ ] No health or medical information
- [ ] No addresses or location data of individuals
- [ ] No social security numbers or government IDs

---

## 📋 Files to Exclude

### Create/Update `.gitignore`
Ensure these patterns are in `.gitignore`:

```gitignore
# Environment variables
.env
.env.local
.env.*.local
.env.production

# Secrets and credentials
secrets/
credentials/
private/
.secrets/
**/secrets/**

# API keys and tokens
*.key
*.pem
*.crt
id_rsa
id_rsa.pub

# Configuration files with secrets
config.local.*
settings.local.*
local.properties

# IDE and local files
.idea/
.vscode/local.settings.json
*.swp
*~

# OS files
.DS_Store
Thumbs.db

# Dependency files that might contain credentials
node_modules/
pip-cache/
.gradle/

# Build artifacts
dist/
build/
*.o
*.so

# Logs
logs/
*.log

# Database files
*.db
*.sqlite
*.sqlite3

# Coverage reports
coverage/
.coverage

# Temporary files
tmp/
temp/
*.tmp
```

---

## 🔍 Pre-Commit Verification

### Before Each Commit
- [ ] Run `git diff HEAD` to review all changes
- [ ] Check for accidentally added sensitive files
- [ ] Verify no secrets in commented-out code
- [ ] Search for common secret patterns:
  - `password =`
  - `api_key =`
  - `secret =`
  - `token =`
  - `AWS_SECRET`
  - `PRIVATE_KEY`

### Search for Secrets Command
```bash
# Check for common secret patterns
grep -r "password\|api_key\|secret\|token\|AWS_SECRET\|PRIVATE_KEY" . \
  --exclude-dir=.git \
  --exclude-dir=node_modules \
  --exclude="*.log" \
  2>/dev/null || echo "No obvious secrets found"

# Check for environment variables that shouldn't be committed
grep -r "\.env" . --exclude-dir=.git 2>/dev/null || echo "No .env files found"
```

---

## 📁 File Size & Binary Content

### Large Files
- [ ] No large binary files (>100MB)
- [ ] No compressed archives with sensitive content
- [ ] Use Git LFS for large files if necessary

### Binary Files
- [ ] No compiled executables
- [ ] No database dumps
- [ ] No backup files

---

## 🛠️ Configuration Examples

### `.env.example` Template
Create this as a template WITHOUT actual values:

```bash
# Database Configuration
DATABASE_URL=postgresql://user:password@localhost/dbname
DATABASE_PASSWORD=your_password_here

# API Keys
API_KEY=your_api_key_here
API_SECRET=your_api_secret_here

# AWS Configuration
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key

# Authentication
JWT_SECRET=your_jwt_secret_here
SESSION_SECRET=your_session_secret_here
```

### `.env.local` (LOCAL ONLY - Never commit)
```bash
# This file is NEVER committed to git
DATABASE_URL=postgresql://user:actual_password@localhost/dbname
API_KEY=actual_api_key_12345
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
```

---

## 🚨 If You Accidentally Committed Secrets

### Immediate Actions
1. **REVOKE immediately** - Rotate all exposed credentials
2. **DO NOT just delete and recommit** - History is still accessible
3. **Use BFG Repo-Cleaner or git-filter-repo**

### Remove Secret from History
```bash
# Using git-filter-repo (recommended)
git filter-repo --replace-text <(echo 'your_secret_token==>***REDACTED***')

# Using BFG
bfg --replace-text secrets.txt repo.git

# Force push (only if you own the repo)
git push origin --force-with-lease
```

### Notify GitHub
- Go to repository Settings
- Alert maintainers of exposed secrets
- Consider using GitHub's secret scanning

---

## 👥 Team Best Practices

### Development Workflow
- [ ] Each developer uses their own `.env.local` file
- [ ] `.env.local` is in `.gitignore`
- [ ] `.env.example` is committed showing required variables
- [ ] Documentation explains how to set up local environment
- [ ] Use environment variable loading libraries (python-dotenv, dotenv, etc.)

### Code Review
- [ ] Reviewers check for hardcoded secrets
- [ ] CI/CD runs secret scanning tools
- [ ] Pre-commit hooks prevent committing secrets
- [ ] Pull request templates include security checklist

---

## 🤖 Automated Tools

### Git Hooks - Pre-commit
Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Prevent committing files with secrets

# Check for .env files
if git diff --cached --name-only | grep -E '\.env|secrets|credentials'; then
    echo "ERROR: Attempting to commit sensitive files!"
    echo "Add these to .gitignore and remove from staging:"
    git diff --cached --name-only | grep -E '\.env|secrets|credentials'
    exit 1
fi

# Check for secret patterns in code
if git diff --cached | grep -E 'password\s*=|api_key\s*=|secret\s*='; then
    echo "WARNING: Found potential secrets in code"
    echo "Review changes carefully before proceeding"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]] || exit 1
fi

exit 0
```

Make executable: `chmod +x .git/hooks/pre-commit`

### GitHub Secret Scanning
- Enable in repository Settings → Security & analysis
- Automatically detects exposed secrets
- Notifies repository owners

### Third-Party Tools
- **TruffleHog** - Scans git history for secrets
- **Detect Secrets** - Prevents committing secrets
- **git-secrets** - Git hooks to prevent committing secrets

---

## 📚 Resources

- [GitHub Security Best Practices](https://docs.github.com/en/code-security)
- [OWASP - Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [git-secrets Documentation](https://github.com/awslabs/git-secrets)
- [TruffleHog GitHub](https://github.com/trufflesecurity/truffleHog)

---

## ✅ Final Verification Checklist

Before pushing to any public repository:

```bash
# 1. Review all changes
git diff HEAD

# 2. Check for .env files
git ls-files | grep -i env

# 3. Search for secrets
git diff HEAD | grep -iE 'password|api_key|secret|token|key'

# 4. Check file history
git log --all --source -- "*/.env" "*/.env.*"

# 5. Verify .gitignore is correct
cat .gitignore | grep -E 'env|secret|credential'

# 6. Final sanity check
git status
```

**Only push when ALL checks pass!** ✓

---

**Last Updated:** 2026-10-03  
**Maintained by:** Security Team  
**Review Frequency:** Quarterly
