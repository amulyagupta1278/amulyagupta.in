# Branch Cleanup Recommendations

**Generated:** 2026-06-06  
**Repository:** amulyagupta1278/amulyagupta.in  
**Governance Lead:** AI Systems Architecture Analysis

---

## Executive Summary

**Repository Status:** ⚠️ **CRITICAL BRANCH SPRAWL**

- **Active Branches:** 2 (main, claude/vibrant-maxwell-eYsY4)
- **Stale Branches:** 33
- **Total Branch Count:** 35

**Recommendation:** Delete all 33 stale branches immediately to restore repository cleanliness.

---

## Current Branch Status

### Active Branches ✅

| Branch | Purpose | Status |
|--------|---------|--------|
| `main` | Production default | Protected, clean |
| `claude/vibrant-maxwell-eYsY4` | PR #15 (SEO fixes) | Active, ready to merge |

### Deleted Branches ✅

| Branch | Reason |
|--------|--------|
| `branch-15-master` (local) | Merged into `claude/vibrant-maxwell-eYsY4`, deleted |

---

## Stale Branches for Deletion

### Category 1: Random Experiment Branches (26 branches)

These are orphaned experiment branches with random suffixes. None were ever merged.

```
remotes/origin/claude/vibrant-maxwell-0R4X5
remotes/origin/claude/vibrant-maxwell-49XBP
remotes/origin/claude/vibrant-maxwell-5p85I
remotes/origin/claude/vibrant-maxwell-AmJqj
remotes/origin/claude/vibrant-maxwell-D4HKY
remotes/origin/claude/vibrant-maxwell-JYZux
remotes/origin/claude/vibrant-maxwell-KE7lr
remotes/origin/claude/vibrant-maxwell-NwFnu
remotes/origin/claude/vibrant-maxwell-Oxpdx
remotes/origin/claude/vibrant-maxwell-Unm00
remotes/origin/claude/vibrant-maxwell-WNSm
remotes/origin/claude/vibrant-maxwell-a2QOO
remotes/origin/claude/vibrant-maxwell-f6AQo
remotes/origin/claude/vibrant-maxwell-gXCUo
remotes/origin/claude/vibrant-maxwell-qStCf
remotes/origin/claude/vibrant-maxwell-rLpgA
remotes/origin/claude/vibrant-maxwell-rTG3n
remotes/origin/claude/vibrant-maxwell-sC4Ha
```

**Action:** DELETE ALL  
**Reason:** Abandoned experiment branches, never merged, no recent commits

---

### Category 2: Named Abandoned Branches (7 branches)

```
remotes/origin/claude/cool-sagan-1xTew
remotes/origin/claude/hopeful-wozniak-0YtQK
remotes/origin/claude/recursing-moore
remotes/origin/claude/setup-google-analytics-console-uPtEh
remotes/origin/fix/fixer-exit-code-bash-e
remotes/origin/fix/meta-tags-forecast-pr-email
remotes/origin/seo-runtime-stable
```

**Action:** DELETE ALL  
**Reason:** Stale feature branches, issues already fixed in PR #15, no recent activity

---

## Deletion Instructions

### Option A: GitHub Web UI (Recommended for Safety)

1. Go to repository → Settings → Branches
2. For each stale branch, click "Delete" button
3. Verify deletion in "All branches" view

### Option B: Command Line (Bulk Deletion)

```bash
# Fetch all branches
git fetch origin

# Delete the 26 random experiment branches
for branch in \
  claude/vibrant-maxwell-0R4X5 \
  claude/vibrant-maxwell-49XBP \
  claude/vibrant-maxwell-5p85I \
  claude/vibrant-maxwell-AmJqj \
  claude/vibrant-maxwell-D4HKY \
  claude/vibrant-maxwell-JYZux \
  claude/vibrant-maxwell-KE7lr \
  claude/vibrant-maxwell-NwFnu \
  claude/vibrant-maxwell-Oxpdx \
  claude/vibrant-maxwell-Unm00 \
  claude/vibrant-maxwell-WNSm \
  claude/vibrant-maxwell-a2QOO \
  claude/vibrant-maxwell-f6AQo \
  claude/vibrant-maxwell-gXCUo \
  claude/vibrant-maxwell-qStCf \
  claude/vibrant-maxwell-rLpgA \
  claude/vibrant-maxwell-rTG3n \
  claude/vibrant-maxwell-sC4Ha
do
  git push origin --delete "$branch" || echo "Failed to delete $branch"
done

# Delete the 7 named branches
git push origin --delete \
  claude/cool-sagan-1xTew \
  claude/hopeful-wozniak-0YtQK \
  claude/recursing-moore \
  claude/setup-google-analytics-console-uPtEh \
  fix/fixer-exit-code-bash-e \
  fix/meta-tags-forecast-pr-email \
  seo-runtime-stable
```

---

## Post-Cleanup Expected State

After deletion:

```
Local Branches:
  * claude/vibrant-maxwell-eYsY4  (PR #15)
    main                          (production)

Remote Branches:
  origin/main
  origin/claude/vibrant-maxwell-eYsY4
```

**Branch Count:** 2 active + 2 remote remotes = **4 total**  
**Stale Branch Count:** 0

---

## Branch Governance Standards (Going Forward)

To prevent future sprawl:

### Naming Convention

Use structured names only:

```
feature/<feature-name>      # New features
bugfix/<issue-name>         # Bug fixes
hotfix/<critical-issue>     # Production hotfixes
docs/<doc-topic>            # Documentation changes
chore/<task-name>           # Internal improvements
```

**Do NOT use:**
- Random suffixes (vibrant-maxwell-xxx)
- Auto-generated IDs (xxx-0R4X5)
- Ambiguous names (update, fix, temp, test)

### Branch Lifecycle

| Stage | Action | Owner |
|-------|--------|-------|
| **Create** | Create feature branch from `main` | Engineer |
| **Work** | Commit and push to feature branch | Engineer |
| **Review** | Open PR, request review | Engineer |
| **Approve** | Merge PR into `main` | Code Reviewer |
| **Cleanup** | Delete feature branch | Engineer (automated via GitHub settings) |
| **Monitor** | Check for stale branches monthly | Git Governance Lead |

### Stale Branch Detection

Branches older than 30 days with no PR:

```bash
# Find branches with no commits in 30 days
git branch -r --format='%(refname:short) %(committerdate:short)' | \
  awk '{if (NF > 1) print $0}' | \
  awk -v cutoff=$(date -d '30 days ago' +%Y-%m-%d) \
    '$NF < cutoff {print "DELETE: " $1}'
```

---

## Governance Enforcement

1. **Before merging to main:** Ensure branch is named per convention
2. **After merging to main:** Automatically delete feature branch (GitHub setting: "Automatically delete head branches")
3. **Monthly audit:** Run stale branch detection
4. **Quarterly review:** Report branch count to team

---

## Impact Assessment

### Before Cleanup
- **Branch Count:** 35
- **Cognitive Load:** High (developers confused by many options)
- **CI/CD Overhead:** Maintains 35 branches in GitHub (storage, API calls)
- **Risk:** Accidental merge from wrong branch

### After Cleanup
- **Branch Count:** 2 active + 2 remote tracking = 4 total
- **Cognitive Load:** Low (only main + current PR branch)
- **CI/CD Overhead:** Minimal
- **Risk:** Eliminated

---

## Next Steps

1. **Immediate:** Delete all 33 stale branches (using GitHub Web UI for safety)
2. **Document:** Add branch governance policy to CONTRIBUTING.md
3. **Automate:** Enable "Automatically delete head branches" in GitHub settings
4. **Monitor:** Set monthly reminder to check for stale branches

---

**Document Owner:** Git Governance Lead  
**Review Required:** Before executing bulk deletion  
**Approval Status:** ⏳ Awaiting authorization
